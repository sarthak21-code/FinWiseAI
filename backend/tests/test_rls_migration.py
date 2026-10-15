import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import app.models  # noqa: F401
from app.db.session import (
    Base,
    SessionLocal,
    _restore_rls_context,
    set_database_context,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_session_rls_context_is_stored_without_postgres_sql_on_sqlite():
    # This uses the suite's disposable SQLite binding. The helper stores only
    # trusted values and does not issue PostgreSQL-specific SQL on SQLite.
    with SessionLocal() as db:
        set_database_context(
            db,
            issuer="https://synthetic.test/auth/v1",
            subject="synthetic-subject",
            identity_id="synthetic-identity-id",
            operator=False,
        )
        context = db.info["finwise_rls_context"]

    assert context == {
        "app.supabase_issuer": "https://synthetic.test/auth/v1",
        "app.supabase_subject": "synthetic-subject",
        "app.user_identity_id": "synthetic-identity-id",
        "app.is_operator": "false",
    }


def test_postgres_transaction_hook_reapplies_only_transaction_local_context():
    calls = []

    class FakeConnection:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement, parameters):
            calls.append((str(statement), parameters))

    identity_context = {
        "app.supabase_issuer": "https://synthetic.test/auth/v1",
        "app.supabase_subject": "synthetic-subject",
        "app.user_identity_id": "synthetic-identity-id",
        "app.is_operator": "false",
    }
    fake_session = SimpleNamespace(info={"finwise_rls_context": identity_context})

    _restore_rls_context(fake_session, None, FakeConnection())

    assert len(calls) == 4
    assert all("set_config(:setting_name, :setting_value, true)" in sql for sql, _ in calls)
    assert {parameters["setting_name"]: parameters["setting_value"] for _, parameters in calls} == identity_context


def test_offline_migrations_match_model_tables_and_emit_rls_and_data_api_revokes(tmp_path):
    ca_certificate = tmp_path / "synthetic-root.crt"
    ca_certificate.write_text("synthetic CA fixture", encoding="ascii")
    database_url = (
        "postgresql+psycopg://postgres.davqezmxaqkxdijkafhj:offline-synthetic@"
        "aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
        f"?sslmode=verify-full&sslrootcert={ca_certificate.as_posix()}"
    )
    child_environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(BACKEND_ROOT),
        "DATABASE_URL": database_url,
        "SUPABASE_URL": "https://davqezmxaqkxdijkafhj.supabase.co",
        "ENVIRONMENT": "development",
    }
    if os.environ.get("SYSTEMROOT"):
        child_environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND_ROOT,
        env=child_environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    sql = result.stdout
    for table_name, table in Base.metadata.tables.items():
        create_match = re.search(
            rf"CREATE TABLE {re.escape(table_name)} \(\n(.*?)\n\);",
            sql,
            re.DOTALL,
        )
        assert create_match, f"Initial schema omitted model table {table_name}"
        table_sql = create_match.group(1)
        for column_name in table.columns.keys():
            in_create = re.search(
                rf"^\s+{re.escape(column_name)}\s+", table_sql, re.MULTILINE
            )
            added_later = (
                f"ALTER TABLE {table_name} ADD COLUMN {column_name}" in sql
            )
            assert in_create or added_later, (
                f"Migration chain omitted model column {table_name}.{column_name}"
            )
        for index in table.indexes:
            assert re.search(
                rf"CREATE (?:UNIQUE )?INDEX {re.escape(index.name)} ON {re.escape(table_name)}\b",
                sql,
                re.IGNORECASE,
            ), f"Migration chain omitted model index {index.name}"

    for table_name in Base.metadata.tables:
        assert f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY" in sql
        assert f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY" in sql
    assert "CREATE ROLE finwise_backend NOLOGIN NOSUPERUSER NOBYPASSRLS" in sql
    assert "REVOKE ALL PRIVILEGES ON TABLE %s FROM %I" in sql
    assert "REVOKE finwise_backend FROM %I" in sql
    assert "pg_has_role(api_role, 'finwise_backend', 'MEMBER')" in sql
    assert "has_table_privilege(" in sql
    assert "has_any_column_privilege(" in sql
    assert "has_schema_privilege(api_role, 'public', 'CREATE')" in sql
    assert "retains effective CREATE on schema public" in sql
    assert sql.index("REVOKE CREATE ON SCHEMA public FROM PUBLIC") < sql.index(
        "IF has_schema_privilege(api_role, 'public', 'CREATE')"
    )
    assert "retains inherited" in sql
    assert "current_setting('app.user_identity_id', true)" in sql
    assert "current_setting('app.is_operator', true) = 'true'" in sql
    assert "finwise_holding_access" in sql
    assert "finwise_financial_documents_read" in sql
    assert "CREATE SCHEMA finwise_migration_private" in sql
    assert "alembic_version_acl_snapshot" in sql
    assert "aclexplode" in sql
    assert "cardinality(a.attacl) > 0" in sql
    assert "array_ndim" not in sql
    assert (
        "REVOKE ALL PRIVILEGES ON TABLE public.alembic_version "
        "FROM anon, authenticated, service_role"
    ) in sql
    assert "REVOKE ALL PRIVILEGES ON TABLE public.alembic_version FROM PUBLIC" not in sql
    assert "API role % retains effective alembic_version access" in sql
    assert "ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin" not in sql

    downgrade = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "downgrade",
            "0004_alembic_api_acl:0003_postgres_rls",
            "--sql",
        ],
        cwd=BACKEND_ROOT,
        env=child_environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert downgrade.returncode == 0, downgrade.stderr
    assert "alembic_version_acl_snapshot" in downgrade.stdout
    assert "GRANT %s ON TABLE public.alembic_version TO %s%s" in downgrade.stdout
    assert "DROP SCHEMA finwise_migration_private" in downgrade.stdout
