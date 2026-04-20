"""Filesystem path anchoring — same bug class as DATABASE_URL.

`renders_dir`, `music_dir`, `remotion_dir` all defaulted to cwd-relative
forms like `./renders` and `../remotion`. That made where renders actually
landed depend on who started the process (uvicorn from backend/ vs. pytest
from tests/). `resolve_repo_root_path` anchors those at the repo root.
"""
from pathlib import Path

from app.paths import resolve_repo_root_path


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
    # Cross-platform absolute path: tmp_path is guaranteed absolute on any
    # OS. A hard-coded POSIX path like "/var/lib/..." would be treated as
    # relative on Windows (no drive letter) and silently anchored.
    abs_path = str(tmp_path.parent / "elsewhere" / "renders")
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

    # Absolute overrides (production) pass through untouched. Use tmp_path
    # for cross-platform absolute form; a POSIX-style "/var/..." is relative
    # on Windows and would get anchored under REPO_ROOT.
    abs_renders = str(tmp_path / "prod-renders")
    prod = Settings(renders_dir=abs_renders)
    assert prod.renders_dir == abs_renders
