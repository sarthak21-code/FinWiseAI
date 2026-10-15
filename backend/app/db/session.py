import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import BACKEND_ROOT, settings
from app.db.safety import ensure_isolated_database_is_safe


# Run before creating the engine so an isolated process cannot initialize the
# protected application database through its startup lifespan.
ensure_isolated_database_is_safe(
    settings.database_url,
    "test" if "pytest" in sys.modules else settings.environment,
    BACKEND_ROOT / "vantageai.db",
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


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
