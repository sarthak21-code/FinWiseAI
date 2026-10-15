"""Apply the reviewed baseline to the explicitly verified disposable project.

Secrets are collected with getpass and held only in process memory. This script
fails closed before DDL unless the live target is empty and matches the fixed
project, TLS, role, and migration-capability expectations.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
import uuid
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from alembic import command
from alembic.config import Config
from psycopg import pq
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

from app.db.safety import (
    ensure_migration_target_is_safe,
    ensure_production_database_is_safe,
)
from scripts.postgres_role_inspection import (
    format_api_role_findings,
    format_runtime_role_finding,
    inspect_api_roles,
    inspect_runtime_role,
)


PROJECT = "davqezmxaqkxdijkafhj"
HOST = "aws-0-ap-south-1.pooler.supabase.com"
PORT = 5432
DATABASE = "postgres"
MIGRATION_LOGIN = f"postgres.{PROJECT}"
RUNTIME_ROLE = "finwise_runtime"
RUNTIME_LOGIN = f"{RUNTIME_ROLE}.{PROJECT}"
SUPABASE_URL = f"https://{PROJECT}.supabase.co"
ALEMBIC_VERSION_TABLE = "alembic_version"
EXPECTED_ALEMBIC_REVISION = "0004_alembic_api_acl"
EXPECTED_TABLES = {
    "user_identities",
    "investor_profiles",
    "portfolio_holdings",
    "analysis_sessions",
    "signal_evaluations",
    "financial_documents",
    "document_chunks",
}
RUNTIME_TABLE_PRIVILEGES = {
    "user_identities": {"SELECT", "INSERT"},
    "investor_profiles": {"SELECT", "INSERT"},
    "portfolio_holdings": {"SELECT", "INSERT"},
    "analysis_sessions": {"SELECT", "INSERT"},
    "signal_evaluations": {"SELECT", "INSERT", "UPDATE"},
    "financial_documents": {"SELECT", "INSERT", "UPDATE"},
    "document_chunks": {"SELECT", "INSERT"},
}
ALL_TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")

_URL_PATTERN = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s\"'<>]+")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|token|secret|api[_-]?key|authorization)\b"
    r"\s*[:=]\s*(?:'[^']*'|\"[^\"]*\"|[^\s,;]+)"
)
_ENV_ASSIGNMENT_PATTERN = re.compile(
    r"\b(?:DATABASE_URL|SUPABASE_URL|[A-Z][A-Z0-9_]*(?:PASSWORD|TOKEN|SECRET|API_KEY))"
    r"\s*=\s*[^\s,;]+"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def _safe_diagnostic_message(message: str) -> str:
    """Keep useful exception text while removing connection and credential material."""
    sanitized = _URL_PATTERN.sub("[URL redacted]", str(message))
    sanitized = _SECRET_ASSIGNMENT_PATTERN.sub("[credential redacted]", sanitized)
    sanitized = _ENV_ASSIGNMENT_PATTERN.sub("[setting redacted]", sanitized)
    sanitized = _BEARER_PATTERN.sub("Bearer [redacted]", sanitized)
    sanitized = _JWT_PATTERN.sub("[token redacted]", sanitized)
    sanitized = " ".join(sanitized.split())
    return sanitized[:600] or "No diagnostic message provided."


def _report_failure(stage: str, error: Exception, *, stream=None) -> None:
    output = stream or sys.stderr
    print(f"setup_failure_stage={stage}", file=output)
    print(f"setup_failure_type={type(error).__name__}", file=output)
    print(
        f"setup_failure_message={_safe_diagnostic_message(str(error))}",
        file=output,
    )


def _validate_migration_table_names(public_table_names) -> None:
    expected_public_tables = EXPECTED_TABLES | {ALEMBIC_VERSION_TABLE}
    if set(public_table_names) != expected_public_tables:
        raise RuntimeError(
            "Public schema table verification failed; expected application tables "
            "plus the Alembic version-control table."
        )


def _validate_alembic_control_table_access(owner: str | None, api_privileges: dict) -> None:
    if owner != "postgres":
        raise RuntimeError("Alembic version table ownership verification failed; expected owner postgres.")
    exposed = {
        role_name: privileges
        for role_name, privileges in api_privileges.items()
        if privileges
    }
    if exposed:
        roles = ", ".join(sorted(exposed))
        raise RuntimeError(
            f"Alembic version table access verification failed; API roles retain privileges: {roles}."
        )


def _validate_runtime_role_state(
    role: dict | None,
    membership_options: list[dict],
    can_replicate: bool,
    table_privileges: dict,
) -> None:
    if not role:
        raise RuntimeError("Runtime role is absent after provisioning.")
    if any(
        (
            role["is_superuser"],
            role["bypasses_rls"],
            role["can_create_database"],
            role["can_create_roles"],
            not role["can_login"],
            role["owns_database"],
            role["public_create"],
            not role["inherits_privileges"],
            can_replicate,
        )
    ):
        raise RuntimeError("Restricted runtime-role attributes are unsafe.")
    if (
        role["direct_memberships"] != ["finwise_backend"]
        or role["effective_memberships"] != ["finwise_backend"]
    ):
        raise RuntimeError("Runtime role memberships are not minimal.")
    if membership_options != [
        {"inherit_option": True, "set_option": False, "admin_option": False}
    ]:
        raise RuntimeError("Runtime membership options are not least privilege.")
    if table_privileges != RUNTIME_TABLE_PRIVILEGES:
        raise RuntimeError("Runtime table privileges differ from the reviewed grant set.")


def _database_url(login: str, password: str, ca_path: Path) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=login,
        password=password,
        host=HOST,
        port=PORT,
        database=DATABASE,
        query={
            "sslmode": "verify-full",
            "sslrootcert": str(ca_path.resolve()),
            "connect_timeout": "10",
        },
    )


def _connection_tls_status(connection, postgres_tls_row) -> dict:
    """Report TLS on both sides of a possible PostgreSQL connection pooler.

    psycopg/libpq reports TLS negotiated by this application connection. The
    PostgreSQL ``pg_stat_ssl`` row reports TLS on the immediate connection to
    the PostgreSQL backend. With Supavisor, these may differ because TLS can
    terminate at the pooler.
    """
    driver_connection = connection.connection.driver_connection
    client_tls_active = driver_connection.pgconn.ssl_in_use is True
    return {
        "client_tls_active": client_tls_active,
        "postgres_backend_tls_active": bool(
            postgres_tls_row is not None and postgres_tls_row["ssl"] is True
        ),
        "postgres_backend_tls_version": (
            postgres_tls_row["version"] if postgres_tls_row is not None else None
        ),
        "postgres_backend_tls_cipher": (
            postgres_tls_row["cipher"] if postgres_tls_row is not None else None
        ),
    }


def _readonly_preflight(engine) -> tuple[bool, dict]:
    with engine.connect() as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            identity = connection.execute(
                text(
                    "SELECT current_database() AS database_name, "
                    "current_user AS current_role, session_user AS login_role, "
                    "current_setting('server_version_num')::integer AS server_version_num"
                )
            ).mappings().one()
            tls = connection.execute(
                text(
                    "SELECT ssl, version, cipher FROM pg_catalog.pg_stat_ssl "
                    "WHERE pid=pg_backend_pid()"
                )
            ).mappings().one_or_none()
            tls_status = _connection_tls_status(connection, tls)
            migration_role = connection.execute(
                text(
                    "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, "
                    "rolcanlogin, has_database_privilege(current_user, "
                    "current_database(), 'CONNECT') AS db_connect "
                    "FROM pg_catalog.pg_roles WHERE rolname=current_user"
                )
            ).mappings().one_or_none()
            database_owner = connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_userbyid(datdba) AS owner, "
                    "current_user=pg_catalog.pg_get_userbyid(datdba) AS is_owner, "
                    "pg_has_role(current_user,'pg_database_owner','USAGE') AS "
                    "database_owner_privileges FROM pg_catalog.pg_database "
                    "WHERE datname=current_database()"
                )
            ).mappings().one_or_none()
            schema = connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_userbyid(nspowner) AS owner, "
                    "pg_has_role(current_user,nspowner,'USAGE') AS owner_privileges, "
                    "has_schema_privilege(current_user,'public','USAGE') AS usage, "
                    "has_schema_privilege(current_user,'public','CREATE') AS create_priv "
                    "FROM pg_catalog.pg_namespace WHERE nspname='public'"
                )
            ).mappings().one_or_none()
            relations = connection.execute(
                text(
                    "SELECT c.relname FROM pg_catalog.pg_class c "
                    "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f') "
                    "ORDER BY c.relname"
                )
            ).scalars().all()
            history_exists = connection.execute(
                text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
            ).scalar_one()
            group_exists = connection.execute(
                text("SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='finwise_backend'")
            ).scalar_one_or_none() is not None
            runtime = inspect_runtime_role(connection)
            api_roles = inspect_api_roles(connection)

    target_matches = (
        identity["database_name"] == DATABASE
        and identity["current_role"] == "postgres"
        and identity["login_role"] == "postgres"
        and identity["server_version_num"] >= 160000
        # sslmode=verify-full is configured in _database_url. Verify the
        # negotiated client-to-pooler channel from libpq itself. pg_stat_ssl
        # can describe a separate pooler-to-PostgreSQL channel and must not be
        # mistaken for the application's TLS state.
        and tls_status["client_tls_active"]
    )
    capabilities = bool(
        migration_role
        and migration_role["rolcreaterole"]
        and migration_role["db_connect"]
        and database_owner
        and database_owner["is_owner"]
        and database_owner["database_owner_privileges"]
        and schema
        and schema["usage"]
        and schema["create_priv"]
        and schema["owner_privileges"]
    )
    api_roles_clear = all(
        role is None or role["public_create"] is False for role in api_roles.values()
    )
    findings = {
        "target_matches": target_matches,
        "migration_capabilities": capabilities,
        "public_relations": list(relations),
        "migration_history_exists": history_exists,
        "finwise_backend_exists": group_exists,
        "runtime_role": runtime,
        "api_roles": api_roles,
        "api_roles_public_create_absent": api_roles_clear,
        "safe": bool(
            target_matches
            and capabilities
            and not relations
            and not history_exists
            and not group_exists
            and runtime is None
            and api_roles_clear
        ),
    }
    print(f"server_database={identity['database_name']}")
    print(f"server_current_role={identity['current_role']}")
    print(f"server_login_role={identity['login_role']}")
    print(f"server_version_num={identity['server_version_num']}")
    print(f"tls_active={tls_status['client_tls_active']}")
    print(f"postgres_backend_tls_active={tls_status['postgres_backend_tls_active']}")
    print(f"postgres_backend_tls_version={tls_status['postgres_backend_tls_version']}")
    print(f"postgres_backend_tls_cipher={tls_status['postgres_backend_tls_cipher']}")
    print(f"migration_role_attributes={dict(migration_role) if migration_role else 'ABSENT'}")
    print(f"database_owner={dict(database_owner) if database_owner else 'UNKNOWN'}")
    print(f"public_schema_privileges={dict(schema) if schema else 'UNKNOWN'}")
    print(f"public_relations={list(relations)}")
    print(f"migration_history_exists={history_exists}")
    print(f"finwise_backend_exists={group_exists}")
    print(format_runtime_role_finding(runtime))
    for line in format_api_role_findings(api_roles):
        print(line)
    print(f"api_roles_effective_public_create_absent={api_roles_clear}")
    print(f"live_preflight_safe={findings['safe']}")
    return findings["safe"], findings


def _validate_0003_resume_findings(findings: dict) -> bool:
    """Accept only the reviewed committed-0003 state for the one-step resume."""
    return bool(
        findings["target_matches"]
        and findings["database_owner_matches"]
        and findings["public_schema_owner_matches"]
        and findings["migration_capabilities"]
        and findings["revision"] == ["0003_postgres_rls"]
        and findings["public_tables"] == EXPECTED_TABLES | {ALEMBIC_VERSION_TABLE}
        and findings["application_tables_owned_and_forced_rls"]
        and findings["policy_count"] == 9
        and findings["constraint_count"] == 18
        and findings["index_count"] == 23
        and findings["backend_role_restricted"]
        and findings["api_roles_restricted"]
        and findings["runtime_role_absent"]
    )


def _resume_0003_preflight(engine) -> tuple[bool, dict]:
    """Read-only guard for the known database where revisions 0001-0003 committed."""
    with engine.connect() as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            identity = connection.execute(
                text(
                    "SELECT current_database() AS database_name, current_user AS current_role, "
                    "session_user AS login_role, current_setting('server_version_num')::integer "
                    "AS server_version_num"
                )
            ).mappings().one()
            backend_tls = connection.execute(
                text("SELECT ssl, version, cipher FROM pg_catalog.pg_stat_ssl WHERE pid=pg_backend_pid()")
            ).mappings().one_or_none()
            client_tls = _connection_tls_status(connection, backend_tls)["client_tls_active"]
            database_owner = connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_userbyid(datdba) AS owner "
                    "FROM pg_catalog.pg_database WHERE datname=current_database()"
                )
            ).scalar_one_or_none()
            public_schema_owner = connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_userbyid(nspowner) "
                    "FROM pg_catalog.pg_namespace WHERE nspname='public'"
                )
            ).scalar_one_or_none()
            public_tables = set(
                connection.execute(
                    text(
                        "SELECT c.relname FROM pg_catalog.pg_class c "
                        "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f') "
                        "ORDER BY c.relname"
                    )
                ).scalars().all()
            )
            revision = (
                connection.execute(
                    text("SELECT version_num FROM public.alembic_version ORDER BY version_num")
                ).scalars().all()
                if ALEMBIC_VERSION_TABLE in public_tables
                else []
            )
            application_rows = connection.execute(
                text(
                    "SELECT c.relname, pg_catalog.pg_get_userbyid(c.relowner) AS owner, "
                    "c.relrowsecurity, c.relforcerowsecurity "
                    "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n "
                    "ON n.oid=c.relnamespace WHERE n.nspname='public' "
                    "AND c.relname = ANY(:tables) AND c.relkind IN ('r','p')"
                ),
                {"tables": list(EXPECTED_TABLES)},
            ).mappings().all()
            policy_count = connection.execute(
                text("SELECT count(*) FROM pg_catalog.pg_policies WHERE schemaname='public'")
            ).scalar_one()
            constraint_count = connection.execute(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_constraint "
                    "WHERE conrelid IN (SELECT c.oid FROM pg_catalog.pg_class c "
                    "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relname=ANY(:tables))"
                ),
                {"tables": list(EXPECTED_TABLES)},
            ).scalar_one()
            index_count = connection.execute(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_index i "
                    "JOIN pg_catalog.pg_class c ON c.oid=i.indrelid "
                    "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relname=ANY(:tables)"
                ),
                {"tables": list(EXPECTED_TABLES)},
            ).scalar_one()
            migration_role = connection.execute(
                text(
                    "SELECT rolcreaterole, has_database_privilege(current_user, "
                    "current_database(), 'CONNECT') AS db_connect "
                    "FROM pg_catalog.pg_roles WHERE rolname=current_user"
                )
            ).mappings().one_or_none()
            backend_role = connection.execute(
                text(
                    "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolcanlogin "
                    "FROM pg_catalog.pg_roles WHERE rolname='finwise_backend'"
                )
            ).mappings().one_or_none()
            backend_role_memberships = connection.execute(
                text(
                    "SELECT ARRAY(SELECT parent.rolname::text FROM pg_catalog.pg_auth_members m "
                    "JOIN pg_catalog.pg_roles member ON member.oid=m.member "
                    "JOIN pg_catalog.pg_roles parent ON parent.oid=m.roleid "
                    "WHERE member.rolname='finwise_backend' ORDER BY parent.rolname) AS direct, "
                    "ARRAY(SELECT candidate.rolname::text FROM pg_catalog.pg_roles candidate "
                    "WHERE candidate.rolname <> 'finwise_backend' AND pg_has_role('finwise_backend', "
                    "candidate.rolname, 'MEMBER') ORDER BY candidate.rolname) AS effective"
                )
            ).mappings().one()
            api_roles = inspect_api_roles(connection)
            runtime_role = inspect_runtime_role(connection)
            app_role_access = {}
            control_role_access = {}
            for role_name, role in api_roles.items():
                if role is None:
                    app_role_access[role_name] = None
                    control_role_access[role_name] = None
                    continue
                table_access = any(
                    connection.execute(
                        text("SELECT has_table_privilege(:role, :table_name, :privilege)"),
                        {
                            "role": role_name,
                            "table_name": f"public.{table_name}",
                            "privilege": privilege,
                        },
                    ).scalar_one()
                    for table_name in EXPECTED_TABLES
                    for privilege in ALL_TABLE_PRIVILEGES
                )
                column_access = any(
                    connection.execute(
                        text(
                            "SELECT has_any_column_privilege(:role, :table_name, :privilege)"
                        ),
                        {
                            "role": role_name,
                            "table_name": f"public.{table_name}",
                            "privilege": privilege,
                        },
                    ).scalar_one()
                    for table_name in EXPECTED_TABLES
                    for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES")
                )
                app_role_access[role_name] = bool(table_access or column_access)
                control_table_access = any(
                    connection.execute(
                        text("SELECT has_table_privilege(:role, 'public.alembic_version', :privilege)"),
                        {"role": role_name, "privilege": privilege},
                    ).scalar_one()
                    for privilege in ALL_TABLE_PRIVILEGES
                )
                control_column_access = any(
                    connection.execute(
                        text("SELECT has_any_column_privilege(:role, 'public.alembic_version', :privilege)"),
                        {"role": role_name, "privilege": privilege},
                    ).scalar_one()
                    for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES")
                )
                control_role_access[role_name] = bool(
                    control_table_access or control_column_access
                )
            findings = {
                "target_matches": (
                    identity["database_name"] == DATABASE
                    and identity["current_role"] == "postgres"
                    and identity["login_role"] == "postgres"
                    and identity["server_version_num"] >= 160000
                    and client_tls
                ),
                "database_owner_matches": database_owner == "postgres",
                "public_schema_owner_matches": public_schema_owner == "pg_database_owner",
                "migration_capabilities": bool(
                    migration_role
                    and migration_role["rolcreaterole"]
                    and migration_role["db_connect"]
                ),
                "revision": revision,
                "public_tables": public_tables,
                "application_tables_owned_and_forced_rls": (
                    {row["relname"] for row in application_rows} == EXPECTED_TABLES
                    and all(
                        row["owner"] == "postgres"
                        and row["relrowsecurity"]
                        and row["relforcerowsecurity"]
                        for row in application_rows
                    )
                ),
                "policy_count": policy_count,
                "constraint_count": constraint_count,
                "index_count": index_count,
                "backend_role_restricted": bool(
                    backend_role
                    and not any(backend_role[key] for key in backend_role)
                    and not backend_role_memberships["direct"]
                    and not backend_role_memberships["effective"]
                ),
                "api_roles_restricted": all(
                    role is not None
                    and not role["public_create"]
                    and "finwise_backend" not in role["effective_memberships"]
                    and not app_role_access[role_name]
                    for role_name, role in api_roles.items()
                ),
                "runtime_role_absent": runtime_role is None,
                "alembic_version_api_access": control_role_access,
            }
    safe = _validate_0003_resume_findings(findings)
    print("preflight_mode=resume_from_0003")
    print(f"resume_state_revision={findings['revision']}")
    print(f"resume_state_tables={sorted(findings['public_tables'])}")
    print(f"resume_target_matches={findings['target_matches']}")
    print(f"resume_rls_and_ownership_match={findings['application_tables_owned_and_forced_rls']}")
    print(f"resume_api_roles_restricted={findings['api_roles_restricted']}")
    print(f"resume_runtime_role_absent={findings['runtime_role_absent']}")
    print(f"resume_alembic_version_api_access={findings['alembic_version_api_access']}")
    print(f"resume_safe_to_apply_pending_0004={safe}")
    return safe, findings


def _verify_migrations(engine) -> None:
    with engine.connect() as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            revisions = connection.execute(
                text("SELECT version_num FROM public.alembic_version ORDER BY version_num")
            ).scalars().all()
            public_tables = connection.execute(
                text(
                    "SELECT c.relname FROM pg_catalog.pg_class c "
                    "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relkind IN ('r','p') "
                    "ORDER BY c.relname"
                )
            ).scalars().all()
            _validate_migration_table_names(public_tables)
            relations = connection.execute(
                text(
                    "SELECT c.relname, pg_catalog.pg_get_userbyid(c.relowner) AS owner, "
                    "c.relrowsecurity, c.relforcerowsecurity "
                    "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n "
                    "ON n.oid=c.relnamespace WHERE n.nspname='public' "
                    "AND c.relkind IN ('r','p') AND c.relname = ANY(:tables) "
                    "ORDER BY c.relname"
                ),
                {"tables": list(EXPECTED_TABLES)},
            ).mappings().all()
            alembic_owner = connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_userbyid(c.relowner) "
                    "FROM pg_catalog.pg_class c WHERE c.oid=to_regclass('public.alembic_version')"
                )
            ).scalar_one_or_none()
            policies = connection.execute(
                text("SELECT count(*) FROM pg_catalog.pg_policies WHERE schemaname='public'")
            ).scalar_one()
            constraint_count = connection.execute(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_constraint "
                    "WHERE conrelid IN (SELECT c.oid FROM pg_catalog.pg_class c "
                    "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relname = ANY(:tables))"
                ),
                {"tables": list(EXPECTED_TABLES)},
            ).scalar_one()
            index_count = connection.execute(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_index i "
                    "JOIN pg_catalog.pg_class c ON c.oid=i.indrelid "
                    "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relname = ANY(:tables)"
                ),
                {"tables": list(EXPECTED_TABLES)},
            ).scalar_one()
            group = connection.execute(
                text(
                    "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolcanlogin "
                    "FROM pg_catalog.pg_roles WHERE rolname='finwise_backend'"
                )
            ).mappings().one_or_none()
            api_roles = inspect_api_roles(connection)
            alembic_api_privileges = {}
            for role_name, role in api_roles.items():
                if role is None:
                    alembic_api_privileges[role_name] = []
                    continue
                effective = [
                    privilege
                    for privilege in ALL_TABLE_PRIVILEGES
                    if connection.execute(
                        text("SELECT has_table_privilege(:role, 'public.alembic_version', :privilege)"),
                        {"role": role_name, "privilege": privilege},
                    ).scalar_one()
                ]
                effective.extend(
                    privilege
                    for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES")
                    if connection.execute(
                        text("SELECT has_any_column_privilege(:role, 'public.alembic_version', :privilege)"),
                        {"role": role_name, "privilege": privilege},
                    ).scalar_one()
                )
                alembic_api_privileges[role_name] = sorted(set(effective))
            api_privilege_findings = {}
            for name, role in api_roles.items():
                if role is None:
                    api_privilege_findings[name] = False
                    continue
                table_privileges = connection.execute(
                    text(
                        "SELECT bool_or(has_table_privilege(:role, 'public.' || table_name, privilege)) "
                        "FROM unnest(CAST(:tables AS text[])) AS t(table_name) "
                        "CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE',"
                        "'REFERENCES','TRIGGER']) AS p(privilege)"
                    ),
                    {"role": name, "tables": list(EXPECTED_TABLES)},
                ).scalar_one()
                column_privileges = connection.execute(
                    text(
                        "SELECT bool_or(has_any_column_privilege(:role, 'public.' || table_name, privilege)) "
                        "FROM unnest(CAST(:tables AS text[])) AS t(table_name) "
                        "CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','REFERENCES']) AS p(privilege)"
                    ),
                    {"role": name, "tables": list(EXPECTED_TABLES)},
                ).scalar_one()
                api_privilege_findings[name] = bool(table_privileges or column_privileges)
    actual_tables = {row["relname"] for row in relations}
    if revisions != [EXPECTED_ALEMBIC_REVISION]:
        raise RuntimeError(
            f"Migration revision verification failed; expected {EXPECTED_ALEMBIC_REVISION}."
        )
    if actual_tables != EXPECTED_TABLES:
        raise RuntimeError("Application table verification failed; actual table set differs from the reviewed schema.")
    _validate_alembic_control_table_access(alembic_owner, alembic_api_privileges)
    if not all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in relations):
        raise RuntimeError("Forced RLS verification failed; one or more application tables are not protected.")
    if any(row["owner"] != "postgres" for row in relations):
        raise RuntimeError("Application table ownership verification failed; owner differs from postgres.")
    if policies != 9:
        raise RuntimeError("RLS policy verification failed; expected nine policies.")
    if constraint_count != 18 or index_count != 23:
        raise RuntimeError("Schema verification failed; constraint or index count differs from the reviewed schema.")
    if not group or any(group[key] for key in ("rolsuper", "rolbypassrls", "rolcreatedb", "rolcreaterole", "rolcanlogin")):
        raise RuntimeError("finwise_backend role verification failed; role is absent or has unsafe attributes.")
    for name, role in api_roles.items():
        if role is not None and (
            role["public_create"]
            or role["effective_memberships"]
            and "finwise_backend" in role["effective_memberships"]
        ):
            raise RuntimeError(f"Data API role verification failed for {name}; access remains too broad.")
        if api_privilege_findings[name]:
            raise RuntimeError(f"Data API privilege verification failed for {name}; application-table grants remain.")
    print(f"alembic_revision={revisions[-1]}")
    print(f"application_tables={sorted(actual_tables)}")
    print(f"table_owners={sorted({row['owner'] for row in relations})}")
    print("all_tables_rls_enabled_and_forced=true")
    print(f"rls_policy_count={policies}")
    print(f"application_constraint_count={constraint_count}")
    print(f"application_index_count={index_count}")
    print("finwise_backend_restricted=true")
    print("api_roles_no_public_create_or_backend_membership=true")


def _provision_runtime(engine, runtime_password: str) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE ROLE finwise_runtime LOGIN INHERIT NOSUPERUSER NOBYPASSRLS "
            "NOCREATEDB NOCREATEROLE NOREPLICATION"
        )
        connection.exec_driver_sql(
            "GRANT finwise_backend TO finwise_runtime WITH INHERIT TRUE, SET FALSE"
        )
        raw = connection.connection.driver_connection
        raw.pgconn.change_password(
            RUNTIME_ROLE.encode("ascii"), runtime_password.encode("utf-8")
        )


def _verify_runtime_role(engine) -> dict:
    with engine.connect() as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            role = inspect_runtime_role(connection)
            membership_options = connection.execute(
                text(
                    "SELECT m.inherit_option, m.set_option, m.admin_option "
                    "FROM pg_catalog.pg_auth_members m "
                    "JOIN pg_catalog.pg_roles member ON member.oid=m.member "
                    "JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid "
                    "WHERE member.rolname='finwise_runtime' "
                    "AND granted.rolname='finwise_backend'"
                )
            ).mappings().all()
            can_replicate = connection.execute(
                text("SELECT rolreplication FROM pg_catalog.pg_roles WHERE rolname='finwise_runtime'")
            ).scalar_one()
            expected = {
                table: {
                    privilege
                    for privilege in ALL_TABLE_PRIVILEGES
                    if connection.execute(
                        text("SELECT has_table_privilege('finwise_runtime', :table_name, :privilege)"),
                        {"table_name": f"public.{table}", "privilege": privilege},
                    ).scalar_one()
                }
                for table in EXPECTED_TABLES
            }
    _validate_runtime_role_state(
        role,
        [dict(item) for item in membership_options],
        can_replicate,
        expected,
    )
    print(format_runtime_role_finding(role))
    print(f"runtime_table_privileges={expected}")
    return role


def _exercise_rls(runtime_url: URL) -> None:
    engine = create_engine(runtime_url, poolclass=NullPool, hide_parameters=True)
    suffix = uuid.uuid4().hex
    identity_a, identity_b = f"{suffix}-a", f"{suffix}-b"
    profile_a, profile_b = f"{suffix}-pa", f"{suffix}-pb"

    def set_context(connection, user_suffix: str, identity_id: str) -> None:
        values = {
            "app.supabase_issuer": f"https://synthetic-{user_suffix}.invalid",
            "app.supabase_subject": f"subject-{user_suffix}-{suffix}",
            "app.user_identity_id": identity_id,
            "app.is_operator": "false",
        }
        for key, value in values.items():
            connection.execute(
                text("SELECT set_config(:key, :value, true)"),
                {"key": key, "value": value},
            )

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                identity_insert = text(
                    "INSERT INTO user_identities (id, issuer, subject, created_at) "
                    "VALUES (:id, :issuer, :subject, now())"
                )
                profile_insert = text(
                    "INSERT INTO investor_profiles (id,name,risk_tolerance,"
                    "investment_horizon_months,max_single_asset_allocation,"
                    "investment_objective,created_at,owner_id,is_demo) VALUES "
                    "(:id,:name,3,36,0.3,'synthetic test',now(),:owner,false)"
                )
                holding_insert = text(
                    "INSERT INTO portfolio_holdings (id,profile_id,symbol,shares,weight,"
                    "cost_basis,asset_category,is_watchlist,created_at) VALUES "
                    "(:id,:profile,'SYN',1,0.1,10,'synthetic',false,now())"
                )
                for label, identity_id, profile_id in (
                    ("a", identity_a, profile_a), ("b", identity_b, profile_b)
                ):
                    issuer = f"https://synthetic-{label}.invalid"
                    subject = f"subject-{label}-{suffix}"
                    set_context(connection, label, "")
                    connection.execute(
                        identity_insert,
                        {"id": identity_id, "issuer": issuer, "subject": subject},
                    )
                    set_context(connection, label, identity_id)
                    connection.execute(
                        profile_insert, {"id": profile_id, "name": f"Synthetic {label}", "owner": identity_id}
                    )
                    connection.execute(
                        holding_insert, {"id": f"{suffix}-h{label}", "profile": profile_id}
                    )

                for label, identity_id, profile_id in (("a", identity_a, profile_a), ("b", identity_b, profile_b)):
                    set_context(connection, label, identity_id)
                    visible_profiles = set(
                        connection.execute(text("SELECT id FROM investor_profiles")).scalars().all()
                    )
                    visible_holdings = set(
                        connection.execute(text("SELECT profile_id FROM portfolio_holdings")).scalars().all()
                    )
                    other_profile = profile_b if label == "a" else profile_a
                    hidden_identity = identity_b if label == "a" else identity_a
                    visible_identities = set(
                        connection.execute(text("SELECT id FROM user_identities")).scalars().all()
                    )
                    savepoint = connection.begin_nested()
                    forged_owner_denied = False
                    try:
                        connection.execute(
                            profile_insert,
                            {
                                "id": f"{suffix}-forged-{label}",
                                "name": "Forged synthetic",
                                "owner": hidden_identity,
                            },
                        )
                    except Exception:
                        forged_owner_denied = True
                    finally:
                        savepoint.rollback()
                    if (
                        visible_profiles != {profile_id}
                        or visible_holdings != {profile_id}
                        or hidden_identity in visible_identities
                        or other_profile in visible_profiles
                        or not forged_owner_denied
                    ):
                        raise RuntimeError("Live RLS ownership assertion failed for synthetic profiles or holdings.")
                transaction.rollback()
            except Exception:
                transaction.rollback()
                raise
    finally:
        engine.dispose()
    print("live_rls_synthetic_user_profile_holding_isolation=PASS (transaction rolled back)")


def _app_health_smoke(runtime_url: URL) -> None:
    import subprocess

    child_env = os.environ.copy()
    child_env.update(
        {
            "DATABASE_URL": runtime_url.render_as_string(hide_password=False),
            "SUPABASE_URL": SUPABASE_URL,
            "SUPABASE_JWT_AUDIENCE": "authenticated",
            "ENVIRONMENT": "production",
        }
    )
    code = """
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    health = client.get('/api/v1/health')
    print('fastapi_health_status=' + str(health.status_code))
    print('fastapi_health_database=' + str(health.json().get('status') if health.status_code == 200 else 'failed'))
    assert health.status_code == 200 and health.json().get('status') == 'ok'
    protected = client.get('/api/v1/users/me')
    print('unauthenticated_user_status=' + str(protected.status_code))
    assert protected.status_code in (401, 403)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if result.returncode != 0:
        # Deliberately omit child stderr: SQLAlchemy/driver errors can include a URL.
        detail = next((line for line in reversed(result.stderr.splitlines()) if line.strip()), "")
        safe_detail = _safe_diagnostic_message(detail) if detail else "No subprocess diagnostic was returned."
        raise RuntimeError(
            f"FastAPI runtime smoke failed with exit code {result.returncode}: {safe_detail}"
        )
    for line in result.stdout.splitlines():
        if line.startswith(("fastapi_health_status=", "fastapi_health_database=", "unauthenticated_user_status=")):
            print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely inspect or prepare FinWiseAI Supabase migrations.")
    parser.add_argument(
        "--ssl-root-cert",
        default=r"C:\Users\Victus\Downloads\prod-ca-2021.crt",
        help="CA certificate path used with sslmode=verify-full",
    )
    parser.add_argument(
        "--read-only-inspect",
        action="store_true",
        help="Inspect the target without executing DDL or application-data writes.",
    )
    parser.add_argument(
        "--resume-from-0003",
        action="store_true",
        help="Resume setup on a verified database with migrations 0001-0003 committed and apply only pending 0004.",
    )
    args = parser.parse_args()
    if not args.read_only_inspect and not hasattr(pq.PGconn, "change_password"):
        print("Stopped before connecting: secure libpq password-change API unavailable.", file=sys.stderr)
        return 2
    ca_path = Path(args.ssl_root_cert).expanduser()
    if not ca_path.is_file():
        print("Stopped before connecting: the specified CA certificate does not exist.", file=sys.stderr)
        return 2

    migration_password = getpass.getpass("Disposable Supabase migration password (hidden): ")
    if not migration_password:
        print("Stopped: migration password was not entered.", file=sys.stderr)
        return 2
    migration_url = _database_url(MIGRATION_LOGIN, migration_password, ca_path)
    migration_url_text = migration_url.render_as_string(hide_password=False)
    try:
        ensure_migration_target_is_safe(migration_url_text, SUPABASE_URL)
    except Exception:
        print("Stopped before connecting: migration target validation failed; details redacted.", file=sys.stderr)
        return 2

    admin_engine = create_engine(migration_url, poolclass=NullPool, hide_parameters=True)
    if args.read_only_inspect:
        stage = "read-only live database inspection"
    elif args.resume_from_0003:
        stage = "resume-from-0003 read-only migration preflight"
    else:
        stage = "initial read-only migration preflight"

    try:
        if args.read_only_inspect:
            _inspect_readonly_database(admin_engine)
            return 0

        if args.resume_from_0003:
            safe, _ = _resume_0003_preflight(admin_engine)
        else:
            safe, _ = _readonly_preflight(admin_engine)

        if not safe:
            print("Stopped before DDL: live target did not satisfy every migration precondition.", file=sys.stderr)
            return 3

        stage = "runtime credential confirmation"
        runtime_password = getpass.getpass("New FinWiseAI runtime password (hidden, 16+ characters): ")
        runtime_confirm = getpass.getpass("Confirm FinWiseAI runtime password (hidden): ")
        if len(runtime_password) < 16 or runtime_password != runtime_confirm:
            print("Stopped before DDL: runtime passwords did not meet confirmation requirements.", file=sys.stderr)
            return 3
        if not hasattr(pq.PGconn, "change_password"):
            print("Stopped before DDL: secure libpq password-change API unavailable.", file=sys.stderr)
            return 2

        # Preserve explicitly configured values only inside this process. Alembic
        # refuses shell/.env fallback and re-validates the exact destination.
        os.environ["DATABASE_URL"] = migration_url_text
        os.environ["SUPABASE_URL"] = SUPABASE_URL
        os.environ["SUPABASE_JWT_AUDIENCE"] = "authenticated"
        os.environ["ENVIRONMENT"] = "development"
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        stage = "Alembic migration execution"
        try:
            if args.resume_from_0003:
                command.upgrade(config, EXPECTED_ALEMBIC_REVISION)
            else:
                command.upgrade(config, "head")
        except Exception as exc:
            _report_failure(stage, exc)
            print("No migration retry attempted; inspect committed migration state before recovery.", file=sys.stderr)
            try:
                _print_migration_state(admin_engine)
            except Exception:
                print("Migration state inspection also failed; diagnostic omitted.", file=sys.stderr)
            return 4

        stage = "post-migration schema and RLS verification"
        _verify_migrations(admin_engine)
        stage = "runtime role provisioning"
        _provision_runtime(admin_engine, runtime_password)
        stage = "runtime role and privilege verification"
        _verify_runtime_role(admin_engine)

        stage = "runtime database target validation"
        runtime_url = _database_url(RUNTIME_LOGIN, runtime_password, ca_path)
        ensure_production_database_is_safe(
            runtime_url.render_as_string(hide_password=False),
            "production",
            SUPABASE_URL,
            "authenticated",
        )
        runtime_engine = create_engine(runtime_url, poolclass=NullPool, hide_parameters=True)
        try:
            stage = "restricted runtime login connection verification"
            with runtime_engine.connect() as connection:
                identity = connection.execute(
                    text("SELECT current_database(), current_user, session_user")
                ).one()
                if identity != (DATABASE, RUNTIME_ROLE, RUNTIME_ROLE):
                    raise RuntimeError("Runtime login identity verification failed; connected role or database differs from the expected restricted target.")
        finally:
            runtime_engine.dispose()
        print("runtime_login_connection=PASS (restricted role, verify-full TLS)")
        stage = "transactional RLS isolation smoke test"
        _exercise_rls(runtime_url)
        stage = "FastAPI runtime health smoke test"
        _app_health_smoke(runtime_url)
        print("setup_result=SUCCESS")
        return 0
    except Exception as exc:
        _report_failure(stage, exc)
        return 5
    finally:
        migration_password = ""
        migration_url_text = ""
        try:
            admin_engine.dispose()
        except Exception:
            pass


def _print_migration_state(engine) -> None:
    with engine.connect() as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            history = connection.execute(
                text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
            ).scalar_one()
            versions = (
                connection.execute(text("SELECT version_num FROM public.alembic_version")).scalars().all()
                if history
                else []
            )
            tables = connection.execute(
                text(
                    "SELECT tablename FROM pg_catalog.pg_tables "
                    "WHERE schemaname='public' ORDER BY tablename"
                )
            ).scalars().all()
    print(f"post_failure_alembic_history_exists={history}")
    print(f"post_failure_alembic_versions={versions}")
    print(f"post_failure_public_tables={tables}")


def _inspect_readonly_database(engine) -> dict:
    """Inspect post-setup state without writing, after proving target and TLS."""
    with engine.connect() as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            identity = connection.execute(
                text(
                    "SELECT current_database() AS database_name, "
                    "current_user AS current_role, session_user AS login_role, "
                    "current_setting('server_version') AS server_version"
                )
            ).mappings().one()
            driver_connection = connection.connection.driver_connection
            actual_host = driver_connection.info.host
            client_tls_active = driver_connection.pgconn.ssl_in_use is True
            backend_tls = connection.execute(
                text(
                    "SELECT ssl, version, cipher FROM pg_catalog.pg_stat_ssl "
                    "WHERE pid=pg_backend_pid()"
                )
            ).mappings().one_or_none()

            # Never inspect schema or roles until both the connected identity
            # and the actual client TLS channel are confirmed.
            identity_matches = (
                identity["database_name"] == DATABASE
                and identity["current_role"] == "postgres"
                and identity["login_role"] == "postgres"
                and actual_host == HOST
            )
            if not identity_matches:
                raise RuntimeError("Read-only inspection stopped: connected database identity did not match the expected target.")
            if not client_tls_active:
                raise RuntimeError("Read-only inspection stopped: client TLS is not active.")

            relations = connection.execute(
                text(
                    "SELECT c.relname, pg_catalog.pg_get_userbyid(c.relowner) AS owner, "
                    "c.relrowsecurity AS rls_enabled, c.relforcerowsecurity AS rls_forced "
                    "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n "
                    "ON n.oid=c.relnamespace WHERE n.nspname='public' "
                    "AND c.relkind IN ('r','p') ORDER BY c.relname"
                )
            ).mappings().all()
            history_exists = connection.execute(
                text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
            ).scalar_one()
            revisions = (
                connection.execute(
                    text("SELECT version_num FROM public.alembic_version ORDER BY version_num")
                ).scalars().all()
                if history_exists
                else []
            )
            alembic_acl = (
                connection.execute(
                    text(
                        "SELECT CASE WHEN acl_item.grantee=0 THEN 'PUBLIC' ELSE grantee.rolname END AS grantee, "
                        "grantor.rolname AS grantor, acl_item.privilege_type, acl_item.is_grantable "
                        "FROM pg_catalog.pg_class c "
                        "CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(c.relacl, "
                        "pg_catalog.acldefault('r', c.relowner))) acl_item "
                        "LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid=acl_item.grantee "
                        "JOIN pg_catalog.pg_roles grantor ON grantor.oid=acl_item.grantor "
                        "WHERE c.oid=to_regclass('public.alembic_version') "
                        "ORDER BY grantee, acl_item.privilege_type"
                    )
                ).mappings().all()
                if history_exists
                else []
            )
            table_default_acl = connection.execute(
                text(
                    "SELECT creator.rolname AS creator_role, "
                    "CASE WHEN acl_item.grantee=0 THEN 'PUBLIC' ELSE grantee.rolname END AS grantee, "
                    "acl_item.privilege_type, acl_item.is_grantable "
                    "FROM pg_catalog.pg_default_acl d "
                    "JOIN pg_catalog.pg_roles creator ON creator.oid=d.defaclrole "
                    "LEFT JOIN pg_catalog.pg_namespace n ON n.oid=d.defaclnamespace "
                    "CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) acl_item "
                    "LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid=acl_item.grantee "
                    "WHERE d.defaclobjtype='r' AND (d.defaclnamespace=0 OR n.nspname='public') "
                    "AND (acl_item.grantee=0 OR grantee.rolname IN ('anon','authenticated','service_role')) "
                    "ORDER BY creator_role, grantee, acl_item.privilege_type"
                )
            ).mappings().all()
            policies = connection.execute(
                text(
                    "SELECT policyname, tablename, cmd, roles FROM pg_catalog.pg_policies "
                    "WHERE schemaname='public' ORDER BY tablename, policyname"
                )
            ).mappings().all()
            schema_privileges = connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_userbyid(nspowner) AS owner, "
                    "has_schema_privilege(current_user,'public','USAGE') AS usage, "
                    "has_schema_privilege(current_user,'public','CREATE') AS create_priv"
                    " FROM pg_catalog.pg_namespace WHERE nspname='public'"
                )
            ).mappings().one()
            database_owner = connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_userbyid(datdba) AS owner, "
                    "current_user=pg_catalog.pg_get_userbyid(datdba) AS is_current_role_owner "
                    "FROM pg_catalog.pg_database WHERE datname=current_database()"
                )
            ).mappings().one()
            current_role_attributes = connection.execute(
                text(
                    "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, "
                    "rolcanlogin, rolinherit, rolreplication "
                    "FROM pg_catalog.pg_roles WHERE rolname=current_user"
                )
            ).mappings().one_or_none()
            migration_role = connection.execute(
                text(
                    "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, "
                    "rolcanlogin, rolinherit, rolreplication "
                    "FROM pg_catalog.pg_roles WHERE rolname='finwise_backend'"
                )
            ).mappings().one_or_none()
            backend_memberships = None
            if migration_role is not None:
                backend_memberships = connection.execute(
                    text(
                        "SELECT ARRAY(SELECT parent.rolname::text FROM pg_catalog.pg_auth_members m "
                        "JOIN pg_catalog.pg_roles parent ON parent.oid=m.roleid "
                        "WHERE m.member=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='finwise_backend') "
                        "ORDER BY parent.rolname) AS direct, "
                        "ARRAY(SELECT candidate.rolname::text FROM pg_catalog.pg_roles candidate "
                        "WHERE candidate.rolname <> 'finwise_backend' AND pg_has_role('finwise_backend',candidate.oid,'MEMBER') "
                        "ORDER BY candidate.rolname) AS effective"
                    )
                ).mappings().one()
            api_roles = inspect_api_roles(connection)
            runtime_role = inspect_runtime_role(connection)
            runtime_replication = (
                connection.execute(
                    text("SELECT rolreplication FROM pg_catalog.pg_roles WHERE rolname='finwise_runtime'")
                ).scalar_one()
                if runtime_role is not None
                else None
            )
            existing_roles = set(
                connection.execute(
                    text(
                        "SELECT rolname FROM pg_catalog.pg_roles WHERE rolname = ANY(:names)"
                    ),
                    {"names": ["postgres", "finwise_backend", RUNTIME_ROLE, "anon", "authenticated", "service_role"]},
                ).scalars().all()
            )
            grants = {}
            for role_name in sorted(existing_roles):
                grants[role_name] = {}
                for relation in relations:
                    table_name = relation["relname"]
                    table_privileges = [
                        privilege
                        for privilege in ALL_TABLE_PRIVILEGES
                        if connection.execute(
                            text("SELECT has_table_privilege(:role_name, :table_name, :privilege)"),
                            {"role_name": role_name, "table_name": f"public.{table_name}", "privilege": privilege},
                        ).scalar_one()
                    ]
                    column_privileges = [
                        privilege
                        for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES")
                        if connection.execute(
                            text("SELECT has_any_column_privilege(:role_name, :table_name, :privilege)"),
                            {"role_name": role_name, "table_name": f"public.{table_name}", "privilege": privilege},
                        ).scalar_one()
                    ]
                    if table_privileges or column_privileges:
                        grants[role_name][table_name] = {
                            "table": table_privileges,
                            "columns": column_privileges,
                        }

    expected_tables_present = EXPECTED_TABLES.intersection(row["relname"] for row in relations)
    actual_table_names = {row["relname"] for row in relations}
    if revisions == [EXPECTED_ALEMBIC_REVISION] and EXPECTED_TABLES.issubset(actual_table_names):
        migration_state_assessment = "ALL_FOUR_REVISIONS_AND_EXPECTED_TABLES_COMMITTED"
    elif revisions == ["0003_postgres_rls"] and EXPECTED_TABLES.issubset(actual_table_names):
        migration_state_assessment = "THREE_REVISIONS_AND_EXPECTED_TABLES_COMMITTED_ACL_FIX_PENDING"
    elif not history_exists and not (EXPECTED_TABLES & actual_table_names):
        migration_state_assessment = "NO_COMMITTED_MIGRATION_ARTIFACTS_VISIBLE"
    else:
        migration_state_assessment = "PARTIAL_OR_INCONSISTENT_COMMITTED_STATE_REQUIRES_MANUAL_REVIEW"
    result = {
        "identity_matches": identity_matches,
        "client_tls_active": client_tls_active,
        "postgres_backend_tls": dict(backend_tls) if backend_tls else "NO_CURRENT_BACKEND_ROW",
        "identity": dict(identity),
        "actual_host": actual_host,
        "migration_history_exists": history_exists,
        "revisions": revisions,
        "migration_state_assessment": migration_state_assessment,
        "alembic_version_acl": [dict(row) for row in alembic_acl],
        "public_table_default_acl": [dict(row) for row in table_default_acl],
        "relations": [dict(row) for row in relations],
        "expected_tables_missing": sorted(EXPECTED_TABLES - expected_tables_present),
        "policies": [dict(row) for row in policies],
        "current_schema_privileges": dict(schema_privileges),
        "database_owner": dict(database_owner),
        "current_role_attributes": dict(current_role_attributes) if current_role_attributes else "UNKNOWN",
        "finwise_backend": dict(migration_role) if migration_role else "ABSENT",
        "finwise_backend_memberships": dict(backend_memberships) if backend_memberships else "ABSENT",
        "finwise_runtime": (
            {**runtime_role, "can_replicate": runtime_replication}
            if runtime_role
            else "ABSENT"
        ),
        "api_roles": api_roles,
        "effective_table_grants": grants,
    }
    print(f"configured_host={HOST}")
    print(f"configured_project_ref={PROJECT}")
    print(f"configured_database={DATABASE}")
    print(f"configured_sslmode=verify-full")
    print(f"actual_host={actual_host}")
    print(f"connected_identity={dict(identity)}")
    print(f"target_identity_matches={identity_matches}")
    print(f"client_tls_active={client_tls_active}")
    print(f"postgres_backend_tls={result['postgres_backend_tls']}")
    print(f"migration_history_exists={history_exists}")
    print(f"alembic_revisions={revisions}")
    print(f"migration_state_assessment={migration_state_assessment}")
    print(f"alembic_version_acl={result['alembic_version_acl']}")
    print(f"public_table_default_acl={result['public_table_default_acl']}")
    print(f"public_relations={result['relations']}")
    print(f"expected_tables_missing={result['expected_tables_missing']}")
    print(f"rls_policies={result['policies']}")
    print(f"current_schema_privileges={dict(schema_privileges)}")
    print(f"database_owner={dict(database_owner)}")
    print(f"migration_login_attributes={result['current_role_attributes']}")
    print(f"finwise_backend={result['finwise_backend']}")
    print(f"finwise_backend_memberships={result['finwise_backend_memberships']}")
    print(f"finwise_runtime={format_runtime_role_finding(runtime_role)}")
    if runtime_role is not None:
        print(f"runtime_role_can_replicate={runtime_replication}")
    for line in format_api_role_findings(api_roles):
        print(line)
    print(f"effective_application_table_grants={grants}")
    print("inspection_mode=READ_ONLY")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
