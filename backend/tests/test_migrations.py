"""Tests for Alembic migration correctness and startup migration guard.

Run from backend/:  python -m pytest tests/test_migrations.py -v

Tests:
  1. Alembic upgrade head against a fresh SQLite DB creates all expected tables.
  2. Alembic downgrade base against a SQLite DB drops all tables.
  3. _check_migrations() emits log.critical when alembic_version is absent
     (simulating a DB created by create_all() without running Alembic).
  4. Postgres integration test — skipped unless TEST_POSTGRES_URL is set.
"""
import logging
import os

import pytest
from sqlalchemy import create_engine, inspect, text


# ─── helpers ─────────────────────────────────────────────────────────────────

def _ini_path():
    return os.path.join(os.path.dirname(__file__), "..", "alembic.ini")


def _alembic_cfg(url: str):
    from alembic.config import Config
    cfg = Config(_ini_path())
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


_EXPECTED_TABLES = {
    "users",
    "unit_templates",
    "scenarios",
    "game_sessions",
    "turn_logs",
    "turn_forecasts",
    "monte_carlo_results",
    "aar_reports",
    "adjudication_logs",
    "token_usage",
}


# ─── test 1: upgrade creates all tables (SQLite) ─────────────────────────────

def test_alembic_upgrade_sqlite_creates_all_tables(tmp_path):
    """alembic upgrade head on a fresh SQLite DB must produce all 10 tables."""
    from alembic.command import upgrade

    db_file = tmp_path / "migration_test.db"
    cfg = _alembic_cfg(f"sqlite:///{db_file}")
    upgrade(cfg, "head")

    eng = create_engine(f"sqlite:///{db_file}")
    try:
        tables = set(inspect(eng).get_table_names())
    finally:
        eng.dispose()

    assert _EXPECTED_TABLES.issubset(tables), (
        f"Missing tables after upgrade: {_EXPECTED_TABLES - tables}"
    )
    assert "alembic_version" in tables


# ─── test 2: downgrade removes all tables (SQLite) ───────────────────────────

def test_alembic_downgrade_base_drops_all_tables(tmp_path):
    """alembic downgrade base must leave an empty DB (alembic_version only)."""
    from alembic.command import downgrade, upgrade

    db_file = tmp_path / "downgrade_test.db"
    cfg = _alembic_cfg(f"sqlite:///{db_file}")
    upgrade(cfg, "head")
    downgrade(cfg, "base")

    eng = create_engine(f"sqlite:///{db_file}")
    try:
        tables = set(inspect(eng).get_table_names())
    finally:
        eng.dispose()

    # After full downgrade none of the domain tables should remain.
    remaining = _EXPECTED_TABLES & tables
    assert not remaining, f"Tables still present after downgrade: {remaining}"


# ─── test 3: _check_migrations warns when alembic_version is absent ──────────

def test_check_migrations_warns_on_pending(tmp_path, caplog):
    """_check_migrations must log CRITICAL when the DB has no alembic_version."""
    import models  # noqa: F401 — registers models on Base.metadata
    from database import Base
    import main

    # Build a DB via create_all() — tables exist but no alembic_version row.
    db_file = tmp_path / "pending.db"
    test_engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=test_engine)

    with caplog.at_level(logging.CRITICAL, logger="theater"):
        main._check_migrations(engine_=test_engine, ini_path_=_ini_path())

    test_engine.dispose()

    assert any("Unapplied" in r.message for r in caplog.records), (
        "Expected a CRITICAL log about unapplied migrations, got: "
        + str([r.message for r in caplog.records])
    )


# ─── test 4: Postgres integration (skipped without TEST_POSTGRES_URL) ────────

@pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRES_URL"),
    reason="Set TEST_POSTGRES_URL=postgresql://... to run the Postgres migration test",
)
def test_alembic_upgrade_postgres_creates_all_tables():
    """alembic upgrade head on a real Postgres DB must produce all 10 tables."""
    from alembic.command import downgrade, upgrade

    url = os.environ["TEST_POSTGRES_URL"]
    cfg = _alembic_cfg(url)

    try:
        upgrade(cfg, "head")
        eng = create_engine(url)
        try:
            tables = set(inspect(eng).get_table_names())
        finally:
            eng.dispose()

        assert _EXPECTED_TABLES.issubset(tables), (
            f"Missing tables after Postgres upgrade: {_EXPECTED_TABLES - tables}"
        )
        assert "alembic_version" in tables
    finally:
        # Always clean up so the test Postgres DB is empty for the next run.
        downgrade(cfg, "base")
