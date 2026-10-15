import sys

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import BACKEND_ROOT, settings
from app.db.safety import (
    ensure_isolated_database_is_safe,
    ensure_production_database_is_safe,
)


# Run before creating the engine so an isolated process cannot initialize the
# protected application database through its startup lifespan.
ensure_isolated_database_is_safe(
    settings.database_url,
    "test" if "pytest" in sys.modules else settings.environment,
    BACKEND_ROOT / "vantageai.db",
)
ensure_production_database_is_safe(
    settings.database_url,
    settings.environment,
    settings.supabase_url,
    settings.supabase_jwt_audience,
)


connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def set_database_context(
    db: Session,
    *,
    issuer: str | None = None,
    subject: str | None = None,
    identity_id: str | None = None,
    operator: bool | None = None,
) -> None:
    """Set trusted, transaction-local context consumed by PostgreSQL RLS.

    Values are saved on the request Session and re-applied at every transaction
    begin because PostgreSQL SET LOCAL state ends at commit/rollback. SQLite
    tests intentionally remain unaffected.
    """
    context = db.info.setdefault("finwise_rls_context", {})
    if issuer is not None:
        context["app.supabase_issuer"] = issuer
    if subject is not None:
        context["app.supabase_subject"] = subject
    if identity_id is not None:
        context["app.user_identity_id"] = identity_id
    if operator is not None:
        context["app.is_operator"] = "true" if operator else "false"

    if db.get_bind().dialect.name == "postgresql" and db.in_transaction():
        _apply_database_context(db.connection(), context)


def _apply_database_context(connection, context: dict[str, str]) -> None:
    for key in (
        "app.supabase_issuer",
        "app.supabase_subject",
        "app.user_identity_id",
        "app.is_operator",
    ):
        connection.execute(
            text("SELECT set_config(:setting_name, :setting_value, true)"),
            {"setting_name": key, "setting_value": context.get(key, "")},
        )


@event.listens_for(Session, "after_begin")
def _restore_rls_context(session: Session, transaction, connection) -> None:
    if connection.dialect.name == "postgresql":
        _apply_database_context(
            connection, session.info.get("finwise_rls_context", {})
        )


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
