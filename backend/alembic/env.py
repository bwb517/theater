import os
import sys

# Ensure backend/ is on sys.path so we can import database and models.
# alembic.ini also sets prepend_sys_path = . for CLI invocations, but the
# Python API (used in tests) does not process that option, so we add it here.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Load .env so that DATABASE_URL is available in os.environ for local dev.
# python-dotenv is in requirements.txt; fail silently if somehow missing.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

# Import Base and all ORM models so autogenerate can diff the full schema.
from database import Base  # noqa: E402
import models  # noqa: E402, F401 — side-effect: registers models on Base.metadata

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False preserves loggers created by the app
    # (e.g. "theater") so that pytest's caplog can still capture them after
    # alembic has loaded its log config.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# URL resolution strategy:
#   - If the Config object's URL was explicitly overridden by the caller
#     (e.g. a test calling cfg.set_main_option before upgrade()), use that value.
#   - Otherwise the URL still equals the ini placeholder, meaning no explicit
#     override was provided: read DATABASE_URL from the environment (production)
#     or fall back to the placeholder (local SQLite dev default).
_INI_PLACEHOLDER = "sqlite:///./theater.db"
_cfg_url = config.get_main_option("sqlalchemy.url")
if _cfg_url == _INI_PLACEHOLDER:
    _cfg_url = os.environ.get("DATABASE_URL") or _INI_PLACEHOLDER
    config.set_main_option("sqlalchemy.url", _cfg_url)


def run_migrations_offline() -> None:
    """Generate SQL without a live DB connection (used for dry-run SQL dumps)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
