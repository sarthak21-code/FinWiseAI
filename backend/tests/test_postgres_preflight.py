from sqlalchemy.engine import URL

import pytest

from scripts import postgres_preflight
from scripts.postgres_preflight import validate_target


def test_preflight_accepts_encoded_password_without_returning_credentials():
    database_url = URL.create(
        "postgresql+psycopg",
        username="finwise_runtime_test.synthetic-ref",
        password="test:p@ss/word%",
        host="aws-0-region.pooler.supabase.com",
        port=5432,
        database="postgres",
        query={"sslmode": "require"},
    ).render_as_string(hide_password=False)

    result = validate_target(
        database_url,
        supabase_url="https://synthetic-ref.supabase.co",
        expected_host="aws-0-region.pooler.supabase.com",
        expected_port=5432,
        expected_database="postgres",
        purpose="runtime",
    )

    assert result.host == "aws-0-region.pooler.supabase.com"
    assert result.database == "postgres"
    assert result.driver == "postgresql+psycopg"
    assert result.configured_identity_matches_project
    assert "test:p@ss/word%" not in repr(result)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"expected_host": "aws-another.pooler.supabase.com"}, "host does not match"),
        ({"expected_database": "production"}, "database does not match"),
        ({"supabase_url": "https://another-ref.supabase.co"}, "login does not match"),
        ({"purpose": "invalid"}, "purpose must be"),
    ],
)
def test_preflight_rejects_mismatched_target_or_purpose(overrides, message):
    database_url = URL.create(
        "postgresql+psycopg",
        username="finwise_runtime_test.synthetic-ref",
        password="synthetic-password",
        host="aws-0-region.pooler.supabase.com",
        port=5432,
        database="postgres",
        query={"sslmode": "require"},
    ).render_as_string(hide_password=False)
    args = {
        "supabase_url": "https://synthetic-ref.supabase.co",
        "expected_host": "aws-0-region.pooler.supabase.com",
        "expected_port": 5432,
        "expected_database": "postgres",
        "purpose": "runtime",
    }
    args.update(overrides)

    with pytest.raises(ValueError, match=message):
        validate_target(database_url, **args)


@pytest.mark.parametrize(
    "username",
    ["postgres.synthetic-ref", "service_role.synthetic-ref", "supabase_admin.synthetic-ref"],
)
def test_preflight_rejects_elevated_runtime_logins(username):
    database_url = URL.create(
        "postgresql+psycopg",
        username=username,
        password="synthetic-password",
        host="aws-0-region.pooler.supabase.com",
        port=5432,
        database="postgres",
        query={"sslmode": "require"},
    ).render_as_string(hide_password=False)

    with pytest.raises(ValueError, match="elevated Supabase login"):
        validate_target(
            database_url,
            supabase_url="https://synthetic-ref.supabase.co",
            expected_host="aws-0-region.pooler.supabase.com",
            expected_port=5432,
            expected_database="postgres",
            purpose="runtime",
        )


def test_preflight_rejects_non_psycopg_driver_and_missing_tls():
    for url in (
        "postgresql://postgres.synthetic-ref:synthetic-password@aws-0-region.pooler.supabase.com:5432/postgres?sslmode=require",
        "postgresql+psycopg://postgres.synthetic-ref:synthetic-password@aws-0-region.pooler.supabase.com:5432/postgres",
    ):
        with pytest.raises(ValueError):
            validate_target(
                url,
                supabase_url="https://synthetic-ref.supabase.co",
                expected_host="aws-0-region.pooler.supabase.com",
                expected_port=5432,
                expected_database="postgres",
                purpose="migration",
            )


def test_migration_preflight_requires_project_admin_login():
    database_url = URL.create(
        "postgresql+psycopg",
        username="finwise_runtime.synthetic-ref",
        password="synthetic-password",
        host="aws-0-region.pooler.supabase.com",
        port=5432,
        database="postgres",
        query={"sslmode": "require"},
    ).render_as_string(hide_password=False)

    with pytest.raises(ValueError, match="migration purpose"):
        validate_target(
            database_url,
            supabase_url="https://synthetic-ref.supabase.co",
            expected_host="aws-0-region.pooler.supabase.com",
            expected_port=5432,
            expected_database="postgres",
            purpose="migration",
        )


def test_cli_preflight_checks_configured_identity_without_printing_credentials(
    monkeypatch, capsys
):
    username = "postgres.synthetic-ref"
    password = "synthetic:p@ss/word%"
    database_url = URL.create(
        "postgresql+psycopg",
        username=username,
        password=password,
        host="aws-0-region.pooler.supabase.com",
        port=5432,
        database="postgres",
        query={"sslmode": "require"},
    ).render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SUPABASE_URL", "https://synthetic-ref.supabase.co")
    monkeypatch.setattr(
        "sys.argv",
        [
            "postgres_preflight.py",
            "--expected-host",
            "aws-0-region.pooler.supabase.com",
            "--expected-port",
            "5432",
            "--expected-database",
            "postgres",
            "--purpose",
            "migration",
        ],
    )

    assert postgres_preflight.main() == 0
    output = capsys.readouterr().out
    assert "configured_login_matches_supabase_project=true" in output
    assert username not in output
    assert password not in output
    assert database_url not in output
