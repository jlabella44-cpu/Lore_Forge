"""Filesystem path normalization.

Lore Forge runs in two shapes today and will grow a third:

1. **Dev monorepo** — `uvicorn` from `backend/`, `alembic` from `db/`, pytest
   from `tests/`. Each one has a different cwd, so a relative default like
   `./renders` or `sqlite:///./lore_forge.sqlite` would land in a different
   place per entry point. `resolve_repo_root_path` fixes that by anchoring
   relative paths at the repo root.

2. **Desktop build (Tauri sidecar)** — the backend is a single binary and
   has no repo to anchor against. Mutable state has to live under the OS
   user-data dir instead (`~/Library/Application Support/LoreForge/` on
   macOS, `%APPDATA%\\LoreForge\\` on Windows). `app_base_dir()` returns
   that path when the desktop mode is signalled.

3. **Container / prod** — explicit absolute paths in env vars, which bypass
   both of the above.

Contract for callers:
    base = app_base_dir()
    if base is not None:
        # desktop mode: write under OS user-data dir
    else:
        # dev mode: anchor relative paths at repo root
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "LoreForge"

# Env vars:
#   LORE_FORGE_USER_DATA_DIR  — explicit override. Tauri sets this before
#                               spawning the sidecar so the app and the
#                               backend agree on the data location.
#   LORE_FORGE_DESKTOP        — "1"/"true" to opt into the platformdirs
#                               default without specifying a path. Use when
#                               the backend is launched as a packaged binary.
_ENV_USER_DATA_DIR = "LORE_FORGE_USER_DATA_DIR"
_ENV_DESKTOP_FLAG = "LORE_FORGE_DESKTOP"


def resolve_repo_root_path(path: str, repo_root: Path) -> str:
    p = Path(path)
    if p.is_absolute():
        return str(p)
    return str((repo_root / p).resolve())


def app_base_dir() -> Path | None:
    """Return the OS user-data directory when running as a desktop app.

    Returns `None` in the dev monorepo so callers know to fall back to
    repo-root anchoring. When non-None, the directory is guaranteed to
    exist on disk.
    """
    explicit = os.environ.get(_ENV_USER_DATA_DIR)
    if explicit:
        base = Path(explicit).expanduser().resolve()
        base.mkdir(parents=True, exist_ok=True)
        return base

    if _is_desktop_mode():
        from platformdirs import user_data_path

        base = user_data_path(APP_NAME, appauthor=False, ensure_exists=True)
        return Path(base)

    return None


def _is_desktop_mode() -> bool:
    return os.environ.get(_ENV_DESKTOP_FLAG, "").strip().lower() in {"1", "true", "yes"}


def resolve_default_path(repo_root_relative: str, base: Path | None, repo_root: Path) -> str:
    """Pick the right anchor for a default path.

    In desktop mode (base is a real directory) the repo-root-relative
    fragment is rewritten against `base`, stripping any leading `./` or
    `backend/` or `../` that only made sense inside the monorepo.
    """
    if base is None:
        return resolve_repo_root_path(repo_root_relative, repo_root)
    leaf = Path(repo_root_relative).name
    return str((base / leaf).resolve())
