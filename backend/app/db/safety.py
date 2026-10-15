from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url


ISOLATED_ENVIRONMENTS = frozenset({"test", "testing", "audit"})
_DATABASE_GUARD_MESSAGE = (
    "Refusing to initialize an isolated environment against the protected "
    "application database. Configure a disposable DATABASE_URL."
)
_PRODUCTION_DATABASE_GUARD_MESSAGE = (
    "Production requires the restricted FinWiseAI runtime login, verified "
    "Supabase Session Pooler target, psycopg driver, sslmode=verify-full, "
    "and an existing CA certificate."
)
_MIGRATION_TARGET_GUARD_MESSAGE = (
    "Alembic requires the verified FinWiseAI Supabase project, migration login, "
    "Session Pooler, PostgreSQL database, sslmode=verify-full, and an existing "
    "CA certificate."
)

EXPECTED_SUPABASE_PROJECT_REF = "davqezmxaqkxdijkafhj"
EXPECTED_SUPABASE_POOLER_HOST = "aws-0-ap-south-1.pooler.supabase.com"
EXPECTED_SUPABASE_DATABASE = "postgres"
EXPECTED_SUPABASE_POOLER_PORT = 5432
EXPECTED_SUPABASE_RUNTIME_LOGIN = f"finwise_runtime.{EXPECTED_SUPABASE_PROJECT_REF}"


def ensure_production_database_is_safe(
    database_url: str,
    environment: str,
    supabase_url: str = "",
    jwt_audience: str = "authenticated",
) -> None:
    """Require the restricted, TLS-verified Supabase target in production."""
    if environment.strip().lower() != "production":
        return

    try:
        url = make_url(database_url)
        ca_certificate = url.query.get("sslrootcert")
        ca_path = Path(ca_certificate).expanduser() if isinstance(ca_certificate, str) else None
        if (
            url.drivername != "postgresql+psycopg"
            or url.username != EXPECTED_SUPABASE_RUNTIME_LOGIN
            or not url.password
            or url.host != EXPECTED_SUPABASE_POOLER_HOST
            or url.port != EXPECTED_SUPABASE_POOLER_PORT
            or url.database != EXPECTED_SUPABASE_DATABASE
            or url.query.get("sslmode") != "verify-full"
            or ca_path is None
            or not ca_path.is_file()
        ):
            raise ValueError
    except Exception:
        # Keep malformed URLs and parser errors from echoing credentials.
        raise RuntimeError(_PRODUCTION_DATABASE_GUARD_MESSAGE) from None

    try:
        supabase_parts = urlsplit(supabase_url)
        if (
            supabase_parts.scheme != "https"
            or supabase_parts.hostname != f"{EXPECTED_SUPABASE_PROJECT_REF}.supabase.co"
            or supabase_parts.port is not None
            or supabase_parts.path not in ("", "/")
            or supabase_parts.username is not None
            or supabase_parts.password is not None
            or supabase_parts.query
            or supabase_parts.fragment
            or not jwt_audience.strip()
        ):
            raise ValueError
    except Exception:
        raise RuntimeError(
            "Production requires SUPABASE_URL over HTTPS for the verified project "
            "and a non-empty SUPABASE_JWT_AUDIENCE."
        ) from None


def ensure_migration_database_is_safe(database_url: str) -> None:
    """Keep Alembic migrations off local SQLite databases by construction."""
    try:
        url = make_url(database_url)
    except Exception:
        raise RuntimeError("Alembic migrations require an explicit PostgreSQL URL.") from None
    if url.drivername != "postgresql+psycopg":
        raise RuntimeError("Alembic migrations require an explicit PostgreSQL URL.")


def ensure_migration_target_is_safe(
    database_url: str | None,
    supabase_url: str | None,
) -> None:
    """Require explicit process settings for the verified migration target.

    This function intentionally reports only a fixed message. In particular,
    URL parsing errors are not chained because driver exceptions can contain
    the URL supplied by the caller.
    """
    if not database_url or not supabase_url:
        raise RuntimeError(_MIGRATION_TARGET_GUARD_MESSAGE)

    try:
        url = make_url(database_url)
        auth_parts = urlsplit(supabase_url)
        project_host = f"{EXPECTED_SUPABASE_PROJECT_REF}.supabase.co"
        if (
            url.drivername != "postgresql+psycopg"
            or url.host != EXPECTED_SUPABASE_POOLER_HOST
            or url.port != EXPECTED_SUPABASE_POOLER_PORT
            or url.database != EXPECTED_SUPABASE_DATABASE
            or url.username != f"postgres.{EXPECTED_SUPABASE_PROJECT_REF}"
            or not url.password
            or auth_parts.scheme != "https"
            or auth_parts.hostname != project_host
            or auth_parts.port is not None
            or auth_parts.path not in ("", "/")
            or auth_parts.username is not None
            or auth_parts.password is not None
            or auth_parts.query
            or auth_parts.fragment
            or url.query.get("sslmode") != "verify-full"
        ):
            raise ValueError

        ca_certificate = url.query.get("sslrootcert")
        if not isinstance(ca_certificate, str) or not ca_certificate.strip():
            raise ValueError
        ca_path = Path(ca_certificate).expanduser()
        if not ca_path.is_file():
            raise ValueError
    except Exception:
        raise RuntimeError(_MIGRATION_TARGET_GUARD_MESSAGE) from None


def ensure_isolated_database_is_safe(
    database_url: str,
    environment: str,
    protected_database_path: Path,
) -> None:
    """Reject the normal SQLite database when running tests or audits."""
    if environment.strip().lower() not in ISOLATED_ENVIRONMENTS:
        return

    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return

    database = url.database
    if not database or database == ":memory:":
        return
    if database.startswith("file:"):
        if ":memory:" in database or url.query.get("mode") == "memory":
            return
        database = database[5:].split("?", maxsplit=1)[0]

    candidate = Path(database).resolve()
    protected = Path(protected_database_path).resolve()
    if candidate == protected:
        raise RuntimeError(_DATABASE_GUARD_MESSAGE)
