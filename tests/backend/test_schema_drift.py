"""Guardrail: `alembic upgrade head` on a fresh DB must match Base.metadata.

Catches the class of bug where a model gains a column or table but nobody writes
the migration — or, conversely, where a migration lands but the model never
does. Without this, the backend silently falls back to `Base.metadata.create_all`
and drifts away from the Alembic-tracked schema (which is how we ended up with
two divergent SQLite files in the first place).
"""
from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "db" / "alembic.ini"


def test_alembic_head_matches_base_metadata(tmp_path, monkeypatch):
    db_path = tmp_path / "drift.sqlite"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(REPO_ROOT / "db"))
    command.upgrade(cfg, "head")

    from app import models  # noqa: F401  (register mappers on Base.metadata)
    from app.db import Base

    # compare_server_default is intentionally off — alembic's server-default
    # diffing is noisy for SQLite (text vs. rendered-SQL clauses) and these
    # mismatches are orthogonal to the schema-divergence class this test
    # guards against. We care about tables, columns, types, nullability.
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(
                conn,
                opts={"compare_type": True},
            )
            diffs = compare_metadata(ctx, Base.metadata)
    finally:
        engine.dispose()

    assert not diffs, (
        "Schema drift between Alembic head and Base.metadata:\n"
        + "\n".join(f"  - {d}" for d in diffs)
    )
