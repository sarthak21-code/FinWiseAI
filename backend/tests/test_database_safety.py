import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.db.safety import ensure_isolated_database_is_safe


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
