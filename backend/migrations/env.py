from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.safety import (
    ensure_migration_database_is_safe,
    ensure_migration_target_is_safe,
)

config = context.config
process_database_url = os.environ.get("DATABASE_URL")
process_supabase_url = os.environ.get("SUPABASE_URL")
ensure_migration_database_is_safe(process_database_url or "")
ensure_migration_target_is_safe(process_database_url, process_supabase_url)

# Validate explicit process-level values before importing Settings, which can
# otherwise fall back to backend/.env. Environment values take precedence, so
# Alembic and the preflight consume the same process configuration.
from app.core.config import settings

if settings.database_url != process_database_url:
    raise RuntimeError("Alembic database configuration is not the explicitly validated target.")

# Reject non-PostgreSQL migration targets before importing session.py, which
# constructs the application SQLAlchemy engine at module import time.
from app.db.session import Base
import app.models  # noqa: F401,E402

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
