"""Validate an explicit PostgreSQL target without opening a connection.

This intentionally reads DATABASE_URL and SUPABASE_URL only from the process
environment. It does not load application Settings (and therefore does not
read backend/.env), import the database session, create an engine, or connect.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

from sqlalchemy.engine import make_url


_SAFE_SSL_MODES = {"require", "verify-ca", "verify-full"}
_ELEVATED_RUNTIME_USERS = {
    "postgres",
    "service_role",
    "supabase_admin",
    "anon",
    "authenticated",
    "authenticator",
    "finwise_backend",
}


@dataclass(frozen=True)
class TargetSummary:
    driver: str
    host: str
    port: int | None
    database: str
    sslmode: str
    purpose: str
    configured_identity_matches_project: bool


def validate_target(
    database_url: str,
    *,
    supabase_url: str,
    expected_host: str,
    expected_port: int,
    expected_database: str,
    purpose: str,
) -> TargetSummary:
    """Validate URL shape and explicit target identity; never connects."""
    if not database_url:
        raise ValueError("DATABASE_URL is not explicitly set in the process environment")
    if purpose not in {"migration", "runtime"}:
        raise ValueError("purpose must be migration or runtime")
    if not expected_host or not expected_database:
        raise ValueError("expected host and database are required")
    if expected_port < 1 or expected_port > 65535:
        raise ValueError("expected port must be between 1 and 65535")

    from urllib.parse import urlsplit

    auth_url = urlsplit(supabase_url)
    if (
        auth_url.scheme != "https"
        or not auth_url.hostname
        or not auth_url.hostname.endswith(".supabase.co")
        or auth_url.path not in ("", "/")
        or auth_url.username
        or auth_url.password
        or auth_url.query
        or auth_url.fragment
    ):
        raise ValueError("SUPABASE_URL must be the HTTPS URL for the intended Supabase project")
    project_ref = auth_url.hostname.removesuffix(".supabase.co")
    if not project_ref or "." in project_ref:
        raise ValueError("SUPABASE_URL does not identify one Supabase project reference")
    if not expected_host.casefold().endswith(".pooler.supabase.com"):
        raise ValueError("--expected-host must identify the Supabase Session Pooler host")
    if expected_port != 5432:
        raise ValueError("Supabase Session Pooler preflight expects port 5432")

    try:
        url = make_url(database_url)
    except Exception as exc:
        raise ValueError("DATABASE_URL is not a valid SQLAlchemy URL") from exc

    if url.drivername != "postgresql+psycopg":
        raise ValueError("DATABASE_URL must use the postgresql+psycopg driver")
    if not url.host or url.host.casefold() != expected_host.casefold():
        raise ValueError("DATABASE_URL host does not match --expected-host")
    if url.port != expected_port:
        raise ValueError("DATABASE_URL port does not match --expected-port")
    if not url.database or url.database != expected_database:
        raise ValueError("DATABASE_URL database does not match --expected-database")
    if not url.username or not url.username.endswith(f".{project_ref}"):
        raise ValueError("DATABASE_URL login does not match the Supabase project reference")
    login_prefix = url.username[: -(len(project_ref) + 1)]
    if not login_prefix:
        raise ValueError("DATABASE_URL must include a pooler login before the project reference")
    if not url.password:
        raise ValueError("DATABASE_URL must include the selected database login credentials")

    query = dict(url.query)
    sslmode = str(query.get("sslmode", "")).lower()
    if sslmode not in _SAFE_SSL_MODES:
        raise ValueError("DATABASE_URL must set sslmode to require, verify-ca, or verify-full")

    if purpose == "runtime":
        login_name = url.username.rsplit(".", maxsplit=1)[0].casefold()
        if login_name in _ELEVATED_RUNTIME_USERS:
            raise ValueError("runtime purpose cannot use a known elevated Supabase login")
    elif url.username.casefold() != f"postgres.{project_ref}".casefold():
        raise ValueError("migration purpose must use the Supabase postgres project login")

    return TargetSummary(
        driver=url.drivername,
        host=url.host,
        port=url.port,
        database=url.database,
        sslmode=sslmode,
        purpose=purpose,
        configured_identity_matches_project=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the explicit PostgreSQL URL target without connecting."
    )
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--expected-port", required=True, type=int)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--purpose", required=True, choices=("migration", "runtime"))
    args = parser.parse_args()

    try:
        target = validate_target(
            os.environ.get("DATABASE_URL", ""),
            supabase_url=os.environ.get("SUPABASE_URL", ""),
            expected_host=args.expected_host,
            expected_port=args.expected_port,
            expected_database=args.expected_database,
            purpose=args.purpose,
        )
    except ValueError as exc:
        print(f"PostgreSQL preflight failed: {exc}", file=sys.stderr)
        return 2

    print("PostgreSQL target preflight passed (no connection attempted).")
    print(f"purpose={target.purpose}")
    print(f"driver={target.driver}")
    print(f"host={target.host}")
    print(f"port={target.port}")
    print(f"database={target.database}")
    print(f"sslmode={target.sslmode}")
    print("configured_login_matches_supabase_project=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
