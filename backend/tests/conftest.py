"""Pytest setup for the THEATER backend test suite.

Runs from the `backend/` directory:  cd backend && python -m pytest

Module-level env vars are set BEFORE any backend module is imported, so
`database.Settings()` binds to a throwaway SQLite file instead of the real
theater.db. This must stay at module scope (not in a fixture) — pytest imports
conftest before collecting test modules that `import database` / `import ai_client`.
"""
import os
import tempfile

_TEST_DB = os.path.join(tempfile.gettempdir(), "theater_pytest.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-0123456789")

import pytest


@pytest.fixture(scope="session", autouse=True)
def _init_test_db():
    """Create a fresh schema for the test DB once per session."""
    import database
    import models

    models.Base.metadata.drop_all(bind=database.engine)
    models.Base.metadata.create_all(bind=database.engine)
    yield
    # Best-effort cleanup of the temp DB file(s)
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(_TEST_DB + suffix)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _clean_token_usage():
    """Empty token_usage between tests so row-count assertions are isolated."""
    import database
    import models

    db = database.SessionLocal()
    try:
        db.query(models.TokenUsage).delete()
        db.commit()
    finally:
        db.close()
    yield
