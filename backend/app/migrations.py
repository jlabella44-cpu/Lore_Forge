"""Programmatic alembic upgrade.

In the dev monorepo, developers run `alembic upgrade head` manually from
`db/`. That's fine for a terminal workflow but the packaged desktop build
has no terminal — the app has to bring its own DB up to `head` on first
launch and on every version upgrade.

`run_migrations_to_head()` drives alembic in-process using the same config
file the CLI uses. It is safe to call on every boot: when the DB is
already at head the operation is a no-op.

Callers:
    - backend/main.py lifespan, when running as a desktop sidecar
    - tests, when a test needs an on-disk DB at head (rare — most tests
      use `Base.metadata.create_all` via tests/conftest.py)
"""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import REPO_ROOT


def run_migrations_to_head() -> None:
    ini_path = REPO_ROOT / "db" / "alembic.ini"
    if not ini_path.exists():
        # Packaged sidecar may ship alembic elsewhere; skip silently rather
        # than crash the app. A future packaging task will bundle the
        # migrations under the sidecar resources dir and update this lookup.
        return

    cfg = Config(str(ini_path))
    # `prepend_sys_path` and `script_location` in alembic.ini are relative
    # to the ini file's directory, so no further rewiring is needed.
    command.upgrade(cfg, "head")
