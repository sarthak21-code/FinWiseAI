from io import StringIO

import pytest
from sqlalchemy.engine import make_url

from scripts.verified_supabase_setup import (
    MIGRATION_LOGIN,
    _database_url,
    _connection_tls_status,
    _report_failure,
    _safe_diagnostic_message,
    _validate_alembic_control_table_access,
    _validate_migration_table_names,
    _validate_runtime_role_state,
    _validate_0003_resume_findings,
    ALEMBIC_VERSION_TABLE,
    EXPECTED_TABLES,
    RUNTIME_TABLE_PRIVILEGES,
)


def test_supabase_setup_url_encodes_special_password_characters(tmp_path):
    certificate = tmp_path / "root certificate.crt"
    certificate.write_text("synthetic certificate", encoding="ascii")
    password = "synthetic:@/ ?#%[]!"

    url = _database_url(MIGRATION_LOGIN, password, certificate)
    parsed = make_url(url.render_as_string(hide_password=False))

    assert parsed.password == password
    assert parsed.host == "aws-0-ap-south-1.pooler.supabase.com"
    assert parsed.database == "postgres"
    assert parsed.query["sslmode"] == "verify-full"
    assert parsed.query["sslrootcert"] == str(certificate.resolve())
    assert "synthetic" not in url.render_as_string(hide_password=True)


class _FakeConnection:
    def __init__(self, client_tls_active):
        self.connection = self
        self.driver_connection = self
        self.pgconn = self
        self.ssl_in_use = client_tls_active


def test_tls_status_uses_client_channel_when_pooler_terminates_tls():
    status = _connection_tls_status(_FakeConnection(True), {"ssl": False, "version": None, "cipher": None})

    assert status == {
        "client_tls_active": True,
        "postgres_backend_tls_active": False,
        "postgres_backend_tls_version": None,
        "postgres_backend_tls_cipher": None,
    }


def test_tls_status_rejects_unencrypted_client_connection():
    status = _connection_tls_status(_FakeConnection(False), {"ssl": False, "version": None, "cipher": None})

    assert status["client_tls_active"] is False
    assert status["postgres_backend_tls_active"] is False


def test_tls_status_handles_missing_postgres_backend_diagnostic():
    status = _connection_tls_status(_FakeConnection(True), None)

    assert status["client_tls_active"] is True
    assert status["postgres_backend_tls_active"] is False


def test_diagnostic_redacts_urls_credentials_environment_values_and_tokens():
    message = (
        "connect failed at postgresql://user:db-pass@example.invalid/postgres "
        "password=another-secret SUPABASE_URL=https://project-secret.invalid "
        "Bearer bearer-secret eyJhbGci.eyJzdWI.signature"
    )

    safe = _safe_diagnostic_message(message)

    assert "connect failed" in safe
    for secret in (
        "db-pass",
        "another-secret",
        "project-secret",
        "bearer-secret",
        "eyJhbGci",
    ):
        assert secret not in safe
    assert "postgresql://" not in safe
    assert "SUPABASE_URL=https://" not in safe


def test_failure_report_includes_stage_type_and_sanitized_message():
    output = StringIO()

    _report_failure(
        "runtime role and privilege verification",
        RuntimeError("runtime grant check failed; password=synthetic-secret"),
        stream=output,
    )

    report = output.getvalue()
    assert "setup_failure_stage=runtime role and privilege verification" in report
    assert "setup_failure_type=RuntimeError" in report
    assert "runtime grant check failed" in report
    assert "synthetic-secret" not in report


def test_migration_verifier_counts_alembic_version_as_control_not_application_table():
    _validate_migration_table_names(EXPECTED_TABLES | {"alembic_version"})


def test_migration_verifier_rejects_unexpected_public_tables():
    try:
        _validate_migration_table_names(EXPECTED_TABLES | {"alembic_version", "unexpected_table"})
    except RuntimeError as exc:
        assert "application tables plus the Alembic version-control table" in str(exc)
    else:
        raise AssertionError("Unexpected public table was accepted")


def test_alembic_control_table_verification_rejects_api_privileges():
    with pytest.raises(RuntimeError, match="API roles retain privileges: anon, authenticated"):
        _validate_alembic_control_table_access(
            "postgres",
            {"anon": ["SELECT"], "authenticated": ["SELECT"], "service_role": []},
        )


def test_alembic_control_table_verification_accepts_owner_only_access():
    _validate_alembic_control_table_access(
        "postgres",
        {"anon": [], "authenticated": [], "service_role": []},
    )


def _safe_runtime_role_fixture():
    return {
        "is_superuser": False,
        "bypasses_rls": False,
        "can_create_database": False,
        "can_create_roles": False,
        "can_login": True,
        "owns_database": False,
        "public_create": False,
        "inherits_privileges": True,
        "direct_memberships": ["finwise_backend"],
        "effective_memberships": ["finwise_backend"],
    }


def test_runtime_role_accepts_only_restricted_backend_membership():
    _validate_runtime_role_state(
        _safe_runtime_role_fixture(),
        [{"inherit_option": True, "set_option": False, "admin_option": False}],
        False,
        RUNTIME_TABLE_PRIVILEGES,
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda role: role.update(is_superuser=True), "attributes are unsafe"),
        (lambda role: role.update(bypasses_rls=True), "attributes are unsafe"),
        (lambda role: role.update(owns_database=True), "attributes are unsafe"),
        (lambda role: role.update(effective_memberships=["finwise_backend", "service_role"]), "memberships are not minimal"),
    ],
)
def test_runtime_role_rejects_elevated_or_extra_membership(mutation, message):
    role = _safe_runtime_role_fixture()
    mutation(role)

    with pytest.raises(RuntimeError, match=message):
        _validate_runtime_role_state(
            role,
            [{"inherit_option": True, "set_option": False, "admin_option": False}],
            False,
            RUNTIME_TABLE_PRIVILEGES,
        )


def test_runtime_role_rejects_set_role_membership_and_extra_table_privileges():
    membership = [{"inherit_option": True, "set_option": True, "admin_option": False}]
    with pytest.raises(RuntimeError, match="membership options are not least privilege"):
        _validate_runtime_role_state(
            _safe_runtime_role_fixture(), membership, False, RUNTIME_TABLE_PRIVILEGES
        )

    extra_privileges = {**RUNTIME_TABLE_PRIVILEGES, "alembic_version": {"SELECT"}}
    with pytest.raises(RuntimeError, match="table privileges differ"):
        _validate_runtime_role_state(
            _safe_runtime_role_fixture(),
            [{"inherit_option": True, "set_option": False, "admin_option": False}],
            False,
            extra_privileges,
        )


def _safe_0003_resume_findings_fixture():
    return {
        "target_matches": True,
        "database_owner_matches": True,
        "public_schema_owner_matches": True,
        "migration_capabilities": True,
        "revision": ["0003_postgres_rls"],
        "public_tables": EXPECTED_TABLES | {ALEMBIC_VERSION_TABLE},
        "application_tables_owned_and_forced_rls": True,
        "policy_count": 9,
        "constraint_count": 18,
        "index_count": 23,
        "backend_role_restricted": True,
        "api_roles_restricted": True,
        "runtime_role_absent": True,
    }


def test_resume_0003_findings_accepts_clean_0003_state():
    findings = _safe_0003_resume_findings_fixture()
    assert _validate_0003_resume_findings(findings) is True


@pytest.mark.parametrize(
    ("key", "invalid_value"),
    [
        ("target_matches", False),
        ("database_owner_matches", False),
        ("public_schema_owner_matches", False),
        ("migration_capabilities", False),
        ("revision", ["0002_user_ownership"]),
        ("revision", ["0003_postgres_rls", "0004_alembic_api_acl"]),
        ("public_tables", EXPECTED_TABLES),
        ("public_tables", EXPECTED_TABLES | {ALEMBIC_VERSION_TABLE, "extra_table"}),
        ("application_tables_owned_and_forced_rls", False),
        ("policy_count", 8),
        ("constraint_count", 17),
        ("index_count", 22),
        ("backend_role_restricted", False),
        ("api_roles_restricted", False),
        ("runtime_role_absent", False),
    ],
)
def test_resume_0003_findings_rejects_divergent_state(key, invalid_value):
    findings = _safe_0003_resume_findings_fixture()
    findings[key] = invalid_value
    assert _validate_0003_resume_findings(findings) is False
