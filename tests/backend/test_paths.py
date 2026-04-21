"""Filesystem path anchoring — same bug class as DATABASE_URL.

`renders_dir`, `music_dir`, `remotion_dir` all defaulted to cwd-relative
forms like `./renders` and `../remotion`. That made where renders actually
landed depend on who started the process (uvicorn from backend/ vs. pytest
from tests/). `resolve_repo_root_path` anchors those at the repo root.
"""
from pathlib import Path

import pytest

from app.paths import app_base_dir, resolve_default_path, resolve_repo_root_path


def test_relative_path_anchors_at_repo_root(tmp_path):
    resolved = resolve_repo_root_path("./renders", tmp_path)
    assert Path(resolved) == (tmp_path / "renders").resolve()


def test_parent_relative_path_is_resolved(tmp_path):
    # `../sibling` relative to a child dir still resolves under tmp_path.
    child = tmp_path / "child"
    child.mkdir()
    resolved = resolve_repo_root_path("../sibling", child)
    assert Path(resolved) == (tmp_path / "sibling").resolve()


def test_absolute_path_passes_through(tmp_path):
    # Platform-appropriate absolute path. On POSIX this is
    # `/var/lib/lore-forge/renders`; on Windows it picks up the current
    # drive anchor (e.g. `C:\var\lib\lore-forge\renders`).
    abs_path = str(Path(tmp_path.anchor) / "var" / "lib" / "lore-forge" / "renders")
    assert resolve_repo_root_path(abs_path, tmp_path) == abs_path


def test_same_relative_path_from_different_cwds_lands_at_same_file(tmp_path):
    """The regression this guards against: uvicorn from backend/ and tests
    from tests/ each resolved `./renders` against their own cwd. With a
    shared repo_root anchor, both land on the same absolute path."""
    repo_root = tmp_path
    from_backend_cwd = resolve_repo_root_path("./renders", repo_root)
    from_tests_cwd = resolve_repo_root_path("./renders", repo_root)
    assert from_backend_cwd == from_tests_cwd
    assert "backend" not in from_backend_cwd
    assert "tests" not in from_backend_cwd


def test_settings_validator_anchors_renderer_paths(tmp_path):
    """Through the pydantic Settings class: relative renderer paths come out
    absolute and anchored at the repo root."""
    from app.config import REPO_ROOT, Settings

    s = Settings(
        renders_dir="./my_renders",
        music_dir="./backend/assets/music",
        remotion_dir="./remotion",
    )
    # All three resolve under REPO_ROOT with no cwd guesswork.
    assert Path(s.renders_dir).is_absolute()
    assert Path(s.music_dir).is_absolute()
    assert Path(s.remotion_dir).is_absolute()
    assert Path(s.renders_dir) == (REPO_ROOT / "my_renders").resolve()
    assert Path(s.music_dir) == (REPO_ROOT / "backend/assets/music").resolve()
    assert Path(s.remotion_dir) == (REPO_ROOT / "remotion").resolve()

    # Absolute overrides (production) pass through untouched.
    abs_renders = str(
        Path(tmp_path.anchor) / "var" / "lib" / "lore-forge" / "renders"
    )
    prod = Settings(renders_dir=abs_renders)
    assert prod.renders_dir == abs_renders


# ---------------------------------------------------------------------------
# Desktop mode: app_base_dir() + resolve_default_path() + Settings validators
# ---------------------------------------------------------------------------


def test_app_base_dir_none_in_dev(monkeypatch):
    """No env var, no desktop flag → dev mode, base is None."""
    monkeypatch.delenv("LORE_FORGE_USER_DATA_DIR", raising=False)
    monkeypatch.delenv("LORE_FORGE_DESKTOP", raising=False)
    assert app_base_dir() is None


def test_app_base_dir_explicit_env_wins(monkeypatch, tmp_path):
    target = tmp_path / "forge-data"
    monkeypatch.setenv("LORE_FORGE_USER_DATA_DIR", str(target))
    monkeypatch.delenv("LORE_FORGE_DESKTOP", raising=False)

    base = app_base_dir()
    assert base == target.resolve()
    assert base.is_dir()  # app_base_dir() creates it


def test_app_base_dir_desktop_flag_uses_platformdirs(monkeypatch, tmp_path):
    """With LORE_FORGE_DESKTOP set and no explicit path, resolve through
    platformdirs. Stub platformdirs.user_data_path to keep the test hermetic."""
    monkeypatch.delenv("LORE_FORGE_USER_DATA_DIR", raising=False)
    monkeypatch.setenv("LORE_FORGE_DESKTOP", "1")

    fake = tmp_path / "fake-platform-dir"

    def _fake_user_data_path(name, appauthor=False, ensure_exists=False):
        assert name == "LoreForge"
        if ensure_exists:
            fake.mkdir(parents=True, exist_ok=True)
        return fake

    import platformdirs

    monkeypatch.setattr(platformdirs, "user_data_path", _fake_user_data_path)

    base = app_base_dir()
    assert base == fake


def test_resolve_default_path_uses_base_when_set(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    resolved = resolve_default_path("./renders", base, tmp_path / "ignored")
    assert Path(resolved) == (base / "renders").resolve()


def test_resolve_default_path_strips_monorepo_prefixes(tmp_path):
    """`./backend/assets/music` in dev lives under REPO_ROOT/backend/assets/music;
    in desktop mode we only want the leaf folder under the user-data dir."""
    base = tmp_path / "base"
    base.mkdir()
    resolved = resolve_default_path("./backend/assets/music", base, tmp_path)
    assert Path(resolved) == (base / "music").resolve()


def test_resolve_default_path_falls_back_to_repo_root_when_no_base(tmp_path):
    resolved = resolve_default_path("./renders", None, tmp_path)
    assert Path(resolved) == (tmp_path / "renders").resolve()


def test_settings_anchor_at_user_data_dir_in_desktop_mode(monkeypatch, tmp_path):
    """When APP_BASE_DIR resolves, renderer paths + sqlite URL all anchor
    under the user-data dir instead of the repo root.

    Monkeypatches `app.config.APP_BASE_DIR` in place rather than reloading
    the module — reloading rebinds `settings` to a new instance that other
    already-imported modules (e.g. `app.services.firecrawl`) don't see,
    which corrupts unrelated tests.
    """
    import app.config as config_module

    target = tmp_path / "desktop"
    target.mkdir()
    monkeypatch.setattr(config_module, "APP_BASE_DIR", target.resolve())

    s = config_module.Settings(
        database_url="sqlite:///./lore_forge.sqlite",
        renders_dir="./renders",
        music_dir="./backend/assets/music",
        remotion_dir="./remotion",
    )
    assert Path(s.renders_dir) == (target / "renders").resolve()
    assert Path(s.music_dir) == (target / "music").resolve()
    assert Path(s.remotion_dir) == (target / "remotion").resolve()
    assert s.database_url == f"sqlite:///{(target / 'lore_forge.sqlite').resolve()}"


@pytest.fixture(autouse=True)
def _clear_desktop_env(monkeypatch):
    """Guard against env leaking between tests in this module."""
    monkeypatch.delenv("LORE_FORGE_USER_DATA_DIR", raising=False)
    monkeypatch.delenv("LORE_FORGE_DESKTOP", raising=False)
