import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from app.db.safety import (
    ensure_migration_database_is_safe,
    ensure_migration_target_is_safe,
    ensure_isolated_database_is_safe,
    ensure_production_database_is_safe,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROTECTED_DATABASE = BACKEND_ROOT / "vantageai.db"


@pytest.mark.parametrize("environment", ["test", "testing", "audit"])
def test_isolated_environment_rejects_protected_database(environment):
    database_url = f"sqlite:///{PROTECTED_DATABASE.as_posix()}"

    with pytest.raises(RuntimeError, match="protected application database"):
        ensure_isolated_database_is_safe(
            database_url,
            environment,
            PROTECTED_DATABASE,
        )


def test_isolated_environment_allows_disposable_sqlite_database(tmp_path):
    disposable_database = tmp_path / "disposable.sqlite3"
    database_url = f"sqlite:///{disposable_database.as_posix()}"
    ensure_isolated_database_is_safe(database_url, "test", PROTECTED_DATABASE)

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()

    assert disposable_database.is_file()


def test_session_import_aborts_before_engine_creation_for_protected_database():
    database_url = f"sqlite:///{PROTECTED_DATABASE.as_posix()}"
    child_environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(BACKEND_ROOT),
        "DATABASE_URL": database_url,
        "ENVIRONMENT": "development",
    }
    if os.environ.get("SYSTEMROOT"):
        child_environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['pytest'] = object(); import app.db.session",
        ],
        cwd=BACKEND_ROOT,
        env=child_environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode != 0
    assert "Refusing to initialize an isolated environment" in result.stderr


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///C:/vantageai/backend/vantageai.db",
        "sqlite:///:memory:",
        "postgresql://db.example/finwiseai",
        "not-a-database-url",
    ],
)
def test_production_rejects_unsafe_or_implicit_database_configuration(database_url):
    with pytest.raises(RuntimeError, match="restricted FinWiseAI runtime login"):
        ensure_production_database_is_safe(database_url, "production")


def _runtime_url(ca_certificate: Path, **overrides: str) -> str:
    values = {
        "drivername": "postgresql+psycopg",
        "username": "finwise_runtime.davqezmxaqkxdijkafhj",
        "password": "synthetic-password",
        "host": "aws-0-ap-south-1.pooler.supabase.com",
        "port": 5432,
        "database": "postgres",
        "query": {"sslmode": "verify-full", "sslrootcert": str(ca_certificate)},
    }
    values.update(overrides)
    return URL.create(**values).render_as_string(hide_password=False)


def test_production_accepts_explicit_restricted_verified_runtime_url(tmp_path):
    ca_certificate = tmp_path / "runtime-root.crt"
    ca_certificate.write_text("synthetic CA fixture", encoding="ascii")
    ensure_production_database_is_safe(
        _runtime_url(ca_certificate),
        "production",
        "https://davqezmxaqkxdijkafhj.supabase.co",
        "authenticated",
    )
    ensure_migration_database_is_safe(
        "postgresql+psycopg://db.example/finwiseai"
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"username": "postgres.davqezmxaqkxdijkafhj"},
        {"username": "service_role.davqezmxaqkxdijkafhj"},
        {"host": "other.pooler.supabase.com"},
        {"database": "other"},
        {"query": {"sslmode": "require", "sslrootcert": "unused"}},
        {"query": {"sslmode": "verify-full", "sslrootcert": "missing.crt"}},
    ],
)
def test_production_rejects_elevated_or_unverified_runtime_url(tmp_path, overrides):
    ca_certificate = tmp_path / "runtime-root.crt"
    ca_certificate.write_text("synthetic CA fixture", encoding="ascii")
    with pytest.raises(RuntimeError, match="restricted FinWiseAI runtime login"):
        ensure_production_database_is_safe(
            _runtime_url(ca_certificate, **overrides),
            "production",
            "https://davqezmxaqkxdijkafhj.supabase.co",
            "authenticated",
        )


def _migration_url(ca_certificate: Path, **overrides: str) -> str:
    values = {
        "drivername": "postgresql+psycopg",
        "username": "postgres.davqezmxaqkxdijkafhj",
        "password": "synthetic-password",
        "host": "aws-0-ap-south-1.pooler.supabase.com",
        "port": 5432,
        "database": "postgres",
        "query": {"sslmode": "verify-full", "sslrootcert": str(ca_certificate)},
    }
    values.update(overrides)
    return URL.create(**values).render_as_string(hide_password=False)


def test_migration_target_guard_accepts_explicit_verified_project_and_ca(tmp_path):
    ca_certificate = tmp_path / "synthetic-root.crt"
    ca_certificate.write_text("synthetic CA fixture", encoding="ascii")

    ensure_migration_target_is_safe(
        _migration_url(ca_certificate),
        "https://davqezmxaqkxdijkafhj.supabase.co",
    )


@pytest.mark.parametrize(
    ("database_overrides", "supabase_url", "create_ca"),
    [
        ({}, None, True),
        ({"database_url": "not-a-url"}, "https://davqezmxaqkxdijkafhj.supabase.co", True),
        ({"host": "other.pooler.supabase.com"}, "https://davqezmxaqkxdijkafhj.supabase.co", True),
        ({"database": "other"}, "https://davqezmxaqkxdijkafhj.supabase.co", True),
        ({"query": {"sslmode": "require", "sslrootcert": "unused"}}, "https://davqezmxaqkxdijkafhj.supabase.co", True),
        ({"query": {"sslmode": "verify-full", "sslrootcert": "missing.crt"}}, "https://davqezmxaqkxdijkafhj.supabase.co", True),
        ({}, "https://another-project.supabase.co", True),
        ({}, "https://davqezmxaqkxdijkafhj.supabase.co", False),
    ],
)
def test_migration_target_guard_rejects_missing_or_mismatched_configuration(
    tmp_path, database_overrides, supabase_url, create_ca
):
    ca_certificate = tmp_path / "synthetic-root.crt"
    if create_ca:
        ca_certificate.write_text("synthetic CA fixture", encoding="ascii")
    if "database_url" in database_overrides:
        database_url = database_overrides["database_url"]
    else:
        database_url = _migration_url(ca_certificate, **database_overrides)

    with pytest.raises(RuntimeError, match="verified FinWiseAI Supabase project"):
        ensure_migration_target_is_safe(database_url, supabase_url)


def test_migration_target_guard_requires_explicit_process_settings():
    with pytest.raises(RuntimeError, match="verified FinWiseAI Supabase project"):
        ensure_migration_target_is_safe(None, None)


@pytest.mark.parametrize("database_url", [
    "sqlite:///C:/vantageai/backend/vantageai.db",
    "sqlite:///:memory:",
    "postgresql://db.example/finwiseai",
])
def test_alembic_refuses_sqlite_or_implicit_postgres_driver(database_url):
    with pytest.raises(RuntimeError, match="Alembic migrations require an explicit PostgreSQL"):
        ensure_migration_database_is_safe(database_url)


def test_alembic_sqlite_guard_runs_before_application_engine_creation(tmp_path):
    engine_sentinel = tmp_path / "migration-engine-created.txt"
    sitecustomize = tmp_path / "sitecustomize.py"
    sitecustomize.write_text(
        "import os, sqlalchemy\n"
        "def mark_engine_creation(*args, **kwargs):\n"
        "    open(os.environ['ENGINE_SENTINEL'], 'w').close()\n"
        "    raise AssertionError('engine creation reached')\n"
        "sqlalchemy.create_engine = mark_engine_creation\n",
        encoding="utf-8",
    )
    child_environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.pathsep.join((str(tmp_path), str(BACKEND_ROOT))),
        "DATABASE_URL": "sqlite:///C:/vantageai/backend/vantageai.db",
        "ENVIRONMENT": "development",
        "ENGINE_SENTINEL": str(engine_sentinel),
    }
    if os.environ.get("SYSTEMROOT"):
        child_environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND_ROOT,
        env=child_environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode != 0
    assert "Alembic migrations require an explicit PostgreSQL URL" in result.stderr
    assert not engine_sentinel.exists()


def test_alembic_requires_explicit_supabase_process_url_before_engine_creation(tmp_path):
    engine_sentinel = tmp_path / "migration-engine-created.txt"
    sitecustomize = tmp_path / "sitecustomize.py"
    sitecustomize.write_text(
        "import os, sqlalchemy\n"
        "def mark_engine_creation(*args, **kwargs):\n"
        "    open(os.environ['ENGINE_SENTINEL'], 'w').close()\n"
        "    raise AssertionError('engine creation reached')\n"
        "sqlalchemy.create_engine = mark_engine_creation\n",
        encoding="utf-8",
    )
    child_environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.pathsep.join((str(tmp_path), str(BACKEND_ROOT))),
        "DATABASE_URL": (
            "postgresql+psycopg://postgres.davqezmxaqkxdijkafhj:synthetic@"
            "aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
        ),
        "ENVIRONMENT": "development",
        "ENGINE_SENTINEL": str(engine_sentinel),
    }
    if os.environ.get("SYSTEMROOT"):
        child_environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=child_environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode != 0
    assert "verified FinWiseAI Supabase project" in result.stderr
    assert "synthetic" not in result.stderr
    assert not engine_sentinel.exists()


@pytest.mark.parametrize(
    "supabase_url,audience",
    [("", "authenticated"), ("http://project.supabase.co", "authenticated"),
     ("https://project.supabase.co", "")],
)
def test_production_rejects_missing_or_unsafe_auth_configuration(
    tmp_path, supabase_url, audience
):
    ca_certificate = tmp_path / "runtime-root.crt"
    ca_certificate.write_text("synthetic CA fixture", encoding="ascii")
    with pytest.raises(RuntimeError, match="SUPABASE_URL over HTTPS"):
        ensure_production_database_is_safe(
            _runtime_url(ca_certificate),
            "production",
            supabase_url,
            audience,
        )


def test_production_session_import_rejects_sqlite_before_engine_creation(tmp_path):
    database_url = f"sqlite:///{PROTECTED_DATABASE.as_posix()}"
    engine_sentinel = tmp_path / "engine-created.txt"
    child_environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(BACKEND_ROOT),
        "DATABASE_URL": database_url,
        "ENVIRONMENT": "production",
        "ENGINE_SENTINEL": str(engine_sentinel),
    }
    if os.environ.get("SYSTEMROOT"):
        child_environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]

    script = """
import os
import sqlalchemy
def mark_engine_creation(*args, **kwargs):
    with open(os.environ['ENGINE_SENTINEL'], 'w', encoding='utf-8') as marker:
        marker.write('called')
    raise AssertionError('engine creation reached')
sqlalchemy.create_engine = mark_engine_creation
import app.db.session
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        env=child_environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode != 0
    assert "restricted FinWiseAI runtime login" in result.stderr
    assert not engine_sentinel.exists()
