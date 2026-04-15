"""Alembic env — imports backend models so autogenerate sees the schema.

`prepend_sys_path = ../backend` in alembic.ini lets us import `app.*`.
DATABASE_URL is read from the .env at the repo root (or env var).
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Load .env at repo root so DATABASE_URL is available.
try:
    from dotenv import load_dotenv

    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")
except ImportError:
    pass

# Ensure backend/ is importable (belt + suspenders alongside prepend_sys_path).
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import Base  # noqa: E402
from app import models  # noqa: E402, F401  (registers mappers on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

db_url = os.getenv("DATABASE_URL", "sqlite:///./lore_forge.sqlite")
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=db_url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg_section = config.get_section(config.config_ini_section, {})
    cfg_section["sqlalchemy.url"] = db_url
    connectable = engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=db_url.startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
