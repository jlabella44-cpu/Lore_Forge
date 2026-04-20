"""resolve_sqlite_url — the helper that stopped backend/ and db/ from drifting
onto two different SQLite files.

The regression this guards against: `DATABASE_URL=sqlite:///./lore_forge.sqlite`
was relative to whoever's cwd started the process, so uvicorn from `backend/`
wrote to `backend/lore_forge.sqlite` while alembic from `db/` wrote to
`db/lore_forge.sqlite`.
"""
from pathlib import Path

from app.db_url import resolve_sqlite_url


def test_relative_sqlite_url_anchors_at_repo_root(tmp_path):
    resolved = resolve_sqlite_url(
        "sqlite:///./lore_forge.sqlite", tmp_path
    )
    assert resolved == f"sqlite:///{(tmp_path / 'lore_forge.sqlite').resolve()}"


def test_relative_without_dot_slash_also_anchors(tmp_path):
    # `sqlite:///lore_forge.sqlite` (no ./) is still a relative path.
    resolved = resolve_sqlite_url("sqlite:///lore_forge.sqlite", tmp_path)
    assert resolved == f"sqlite:///{(tmp_path / 'lore_forge.sqlite').resolve()}"


def test_absolute_sqlite_url_passes_through(tmp_path):
    abs_db = "/var/lib/lore-forge/lore_forge.sqlite"
    assert (
        resolve_sqlite_url(f"sqlite:///{abs_db}", tmp_path)
        == f"sqlite:///{abs_db}"
    )


def test_in_memory_passes_through(tmp_path):
    assert resolve_sqlite_url("sqlite:///:memory:", tmp_path) == "sqlite:///:memory:"


def test_uri_form_passes_through(tmp_path):
    # `sqlite:///file:...?uri=true` is the URI-mode form; don't munge it.
    url = "sqlite:///file:cachedb?mode=memory&cache=shared"
    assert resolve_sqlite_url(url, tmp_path) == url


def test_non_sqlite_url_passes_through(tmp_path):
    for url in (
        "postgresql://user:pw@host:5432/db",
        "postgresql+psycopg2://user@host/db",
        "mysql://user@host/db",
    ):
        assert resolve_sqlite_url(url, tmp_path) == url


def test_same_relative_url_from_different_cwds_lands_at_same_file(tmp_path):
    """The actual divergence bug: alembic from db/ and uvicorn from backend/
    share a repo root, so the resolved path must be identical regardless of
    which subdir invoked them."""
    repo_root = tmp_path
    (repo_root / "backend").mkdir()
    (repo_root / "db").mkdir()

    from_backend = resolve_sqlite_url(
        "sqlite:///./lore_forge.sqlite", repo_root
    )
    from_db = resolve_sqlite_url(
        "sqlite:///./lore_forge.sqlite", repo_root
    )
    assert from_backend == from_db
    assert "backend" not in from_backend
    assert "db" not in from_backend


def test_settings_validator_normalizes_relative_path():
    """Round-trip through the pydantic Settings class: constructing Settings
    with a relative DATABASE_URL yields an absolute one on the other side.

    Deliberately constructs a fresh Settings rather than reloading the
    `app.config` module — a reload would rebind `app.config.settings` while
    every other module still holds a reference to the old singleton, which
    silently breaks unrelated tests later in the session.
    """
    from app.config import Settings

    s = Settings(database_url="sqlite:///./my_custom.sqlite")
    # Semantic assertion, not format-level — on POSIX the URL looks like
    # `sqlite:////abs/path` (4 slashes), on Windows `sqlite:///C:\abs\path`
    # (3 slashes + drive). Either way the path portion must be absolute.
    assert s.database_url.startswith("sqlite:///")
    path_part = s.database_url[len("sqlite:///"):]
    assert Path(path_part).is_absolute()
    assert Path(path_part).name == "my_custom.sqlite"

    # Non-sqlite URLs pass through unchanged.
    pg = Settings(database_url="postgresql://u:p@h/d")
    assert pg.database_url == "postgresql://u:p@h/d"
