from pathlib import Path

from sqlalchemy.engine import make_url


ISOLATED_ENVIRONMENTS = frozenset({"test", "testing", "audit"})
_DATABASE_GUARD_MESSAGE = (
    "Refusing to initialize an isolated environment against the protected "
    "application database. Configure a disposable DATABASE_URL."
)


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
