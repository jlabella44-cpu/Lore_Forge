"""DATABASE_URL normalization.

Lore Forge defaults to `sqlite:///./lore_forge.sqlite`, a path that is
relative to the current working directory. That's how the backend (run from
`backend/`) and alembic (run from `db/`) ended up writing to two different
SQLite files — same URL string, two different absolute locations.

`resolve_sqlite_url` converts a relative SQLite URL into an absolute one,
anchored either at the OS user-data dir (desktop build) or the repo root
(dev). Non-SQLite URLs, `:memory:`, and already-absolute SQLite URLs are
returned unchanged.

Invariant: after this, every entry point (uvicorn from `backend/`, alembic
from `db/`, tests, CI, packaged sidecar) resolves the same URL to the same
file on disk.
"""
from __future__ import annotations

from pathlib import Path

SQLITE_TRIPLE = "sqlite:///"


def resolve_sqlite_url(url: str, repo_root: Path, base_dir: Path | None = None) -> str:
    if not url.startswith(SQLITE_TRIPLE):
        # postgresql://, mysql://, sqlite:// (no path), etc. — leave alone.
        return url

    path_part = url[len(SQLITE_TRIPLE):]

    # In-memory and URI forms: sqlite:///:memory:, sqlite:///file:...
    if not path_part or path_part == ":memory:" or path_part.startswith("file:"):
        return url

    # Already absolute: sqlite:////var/lib/x.sqlite strips to "/var/lib/x.sqlite".
    if path_part.startswith("/"):
        return url

    # Desktop build: the repo doesn't exist on the end-user's machine, so a
    # relative default like "./lore_forge.sqlite" has to land under the OS
    # user-data dir instead. `base_dir` is the prepared directory from
    # `app.paths.app_base_dir()`.
    if base_dir is not None:
        leaf = Path(path_part).name
        abs_path = (base_dir / leaf).resolve()
        return f"{SQLITE_TRIPLE}{abs_path}"

    abs_path = (repo_root / path_part).resolve()
    return f"{SQLITE_TRIPLE}{abs_path}"
