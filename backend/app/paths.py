"""Filesystem path normalization.

Lore Forge's settings default several paths to relative forms:
`RENDERS_DIR=./renders`, `MUSIC_DIR=./assets/music`, `REMOTION_DIR=../remotion`.
Like the old `DATABASE_URL=sqlite:///./lore_forge.sqlite`, these resolve
against the cwd of whoever started the process — which means renders written
by uvicorn (cwd=backend/) land in a different place than renders served by
tests (cwd=tests/).

`resolve_repo_root_path` anchors a relative path to the repo root so every
entry point sees the same absolute location. Already-absolute paths pass
through unchanged.
"""
from __future__ import annotations

from pathlib import Path


def resolve_repo_root_path(path: str, repo_root: Path) -> str:
    p = Path(path)
    if p.is_absolute():
        return str(p)
    return str((repo_root / p).resolve())
