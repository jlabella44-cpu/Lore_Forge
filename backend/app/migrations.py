"""Programmatic alembic upgrade.

In the dev monorepo, developers run `alembic upgrade head` manually from
`db/`. That's fine for a terminal workflow but the packaged desktop build
has no terminal — the app has to bring its own DB up to `head` on first
launch and on every version upgrade.

`run_migrations_to_head()` drives alembic in-process. It is safe to call
on every boot: when the DB is already at head the operation is a no-op.

Migrations location lookup order:
  1. Dev monorepo        → `<REPO_ROOT>/db/alembic.ini`
  2. PyInstaller bundle  → `<sys._MEIPASS>/db/alembic.ini` (the spec
     bundles `db/` as data so alembic's env + versions/ ride along with
     the frozen backend)

Callers:
    - backend/main.py lifespan, when running as a desktop sidecar
    - tests, when a test needs an on-disk DB at head (rare — most tests
      use `Base.metadata.create_all` via tests/conftest.py)
"""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import REPO_ROOT


def _locate_alembic_ini() -> Path | None:
    candidates = [REPO_ROOT / "db" / "alembic.ini"]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        # PyInstaller unpacks datas to a temp dir at _MEIPASS; the spec
        # bundles `db/` there so the ini + env.py + versions/ travel
        # with the frozen backend.
        candidates.append(Path(meipass) / "db" / "alembic.ini")
    for c in candidates:
        if c.exists():
            return c
    return None


def run_migrations_to_head() -> None:
    ini_path = _locate_alembic_ini()
    if ini_path is None:
        # Packaging bug or someone imported the helper without the
        # migrations bundled. Fail fast rather than silently leave the
        # DB at the wrong revision.
        raise RuntimeError(
            "alembic.ini not found — db/ must be bundled alongside the sidecar"
        )

    cfg = Config(str(ini_path))
    # alembic.ini uses `script_location = .`, which is resolved against
    # the CWD — fine when running `alembic upgrade head` from db/ in a
    # terminal, but the in-process caller is usually the repo root or a
    # PyInstaller temp dir. Pin the location to the ini file's parent so
    # the lookup is stable regardless of CWD.
    cfg.set_main_option("script_location", str(ini_path.parent))
    command.upgrade(cfg, "head")
