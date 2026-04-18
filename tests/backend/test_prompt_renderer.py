"""prompt_renderer + migration 0012: Books profile prompts JSON."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.profile import Profile
from app.services import llm, prompt_renderer
from app.services.prompts import short_hook


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Pure rendering primitive
# ---------------------------------------------------------------------------


def test_render_substitutes_variables():
    out = prompt_renderer.render(
        "You write {{entity_type}} trailer videos for {{audience}}.",
        {"entity_type": "film", "audience": "cinephiles"},
    )
    assert out == "You write film trailer videos for cinephiles."


def test_render_strict_undefined_raises_on_typo():
    import jinja2

    with pytest.raises(jinja2.UndefinedError):
        prompt_renderer.render("Hello {{name}}", {"nmae": "x"})


def test_render_no_variables_is_identity():
    # A template with no placeholders passes through byte-for-byte —
    # important: migration 0012 seeds Books prompts as plain strings
    # (no Jinja vars yet), and rendering them must produce the exact
    # original text.
    raw = short_hook.HOOKS_SYSTEM
    assert prompt_renderer.render(raw, {}) == raw


def test_get_system_prompt_raises_when_profile_missing(tmp_path):
    session = _fresh_session(tmp_path)
    with pytest.raises(KeyError, match="nosuchprofile"):
        prompt_renderer.get_system_prompt(session, "nosuchprofile", "hook_system")


def test_get_system_prompt_raises_when_stage_missing(tmp_path):
    session = _fresh_session(tmp_path)
    session.add(
        Profile(
            slug="empty",
            name="Empty",
            entity_label="Thing",
            prompts={},
            sources_config=[],
            taxonomy=[],
            cta_fields=[],
            render_tones={},
        )
    )
    session.commit()
    with pytest.raises(KeyError, match="hook_system"):
        prompt_renderer.get_system_prompt(session, "empty", "hook_system")


def test_get_system_prompt_renders_with_vars(tmp_path):
    session = _fresh_session(tmp_path)
    session.add(
        Profile(
            slug="films",
            name="Films",
            entity_label="Film",
            prompts={"hook_system": "Write {{entity}} trailers."},
            sources_config=[],
            taxonomy=[],
            cta_fields=[],
            render_tones={},
        )
    )
    session.commit()
    out = prompt_renderer.get_system_prompt(
        session, "films", "hook_system", {"entity": "film"}
    )
    assert out == "Write film trailers."


# ---------------------------------------------------------------------------
# Migration 0012: Books profile prompts seeded byte-for-byte
# ---------------------------------------------------------------------------


def test_migration_0012_populates_books_prompts(tmp_path):
    db_file = tmp_path / "b4.sqlite"
    url = f"sqlite:///{db_file}"

    env = os.environ.copy()
    env["DATABASE_URL"] = url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(REPO_ROOT / "db"),
        env=env,
        check=True,
        capture_output=True,
    )

    engine = create_engine(url)
    try:
        with sessionmaker(bind=engine)() as s:
            books = s.query(Profile).filter(Profile.slug == "books").one()
            prompts = books.prompts
            # All four stages present and populated.
            assert set(prompts) >= {
                "hook_system",
                "script_system",
                "scene_prompts_system",
                "meta_system",
            }
            for v in prompts.values():
                assert v  # non-empty

            # Byte-for-byte match with the canonical live constants.
            # This is the snapshot contract: the migration must encode
            # the current prompts verbatim, otherwise callers that
            # later migrate through prompt_renderer would see a
            # different LLM input than the legacy direct-import path.
            # Three stages match the prompts/short_hook.py constants.
            # scene_prompts_system was reconciled by migration 0013 to
            # the canonical llm.py version (slightly more verbose);
            # see 0013's module docstring.
            assert prompts["hook_system"] == short_hook.HOOKS_SYSTEM
            assert prompts["script_system"] == short_hook.SCRIPT_SYSTEM
            assert (
                prompts["scene_prompts_system"] == llm._SCENE_PROMPTS_SYSTEM
            )
            assert prompts["meta_system"] == short_hook.META_SYSTEM

            # render() over each should round-trip unchanged (no Jinja
            # variables present).
            for key, raw in prompts.items():
                assert prompt_renderer.render(raw, {}) == raw
    finally:
        engine.dispose()


def test_migration_0012_preserves_operator_edits(tmp_path):
    """If a previous operator edited Books.prompts between 0009 and
    0012, re-running the migration must not overwrite their changes.
    """
    db_file = tmp_path / "b4-edit.sqlite"
    url = f"sqlite:///{db_file}"

    env = os.environ.copy()
    env["DATABASE_URL"] = url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "0011_cta_links"],
        cwd=str(REPO_ROOT / "db"),
        env=env,
        check=True,
        capture_output=True,
    )

    import json

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "UPDATE profiles SET prompts = ? WHERE slug = 'books'",
                (json.dumps({"hook_system": "OPERATOR WROTE THIS"}),),
            )
    finally:
        engine.dispose()

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(REPO_ROOT / "db"),
        env=env,
        check=True,
        capture_output=True,
    )

    engine = create_engine(url)
    try:
        with sessionmaker(bind=engine)() as s:
            books = s.query(Profile).filter(Profile.slug == "books").one()
            assert books.prompts["hook_system"] == "OPERATOR WROTE THIS"
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tmp.sqlite'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()
