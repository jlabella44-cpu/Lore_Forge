"""llm.py routes system prompts through the active profile."""
from __future__ import annotations

from unittest.mock import patch

from app import db as db_module
from app.models import Profile
from app.services import llm


def SessionLocal():
    # Read via attribute so pytest fixtures that swap
    # `db_module.SessionLocal` take effect.
    return db_module.SessionLocal()


def test_profile_prompt_falls_back_to_default_when_no_db():
    """If SessionLocal can't be reached (e.g. a unit test running this
    module in isolation), the module-constant default wins."""
    with patch.object(
        db_module,
        "SessionLocal",
        side_effect=RuntimeError("simulated db failure"),
    ):
        assert (
            llm._profile_prompt("hook_system", "DEFAULT")
            == "DEFAULT"
        )


def test_profile_prompt_returns_default_when_no_active(client):
    from sqlalchemy import update

    db = SessionLocal()
    try:
        db.execute(update(Profile).values(active=False))
        db.commit()
    finally:
        db.close()

    assert (
        llm._profile_prompt("hook_system", "DEFAULT")
        == "DEFAULT"
    )


def test_profile_prompt_returns_default_when_stage_missing(client):
    """Books profile has some prompts but not 'missing_stage'."""
    assert (
        llm._profile_prompt("missing_stage", "FALLBACK")
        == "FALLBACK"
    )


def test_profile_prompt_reads_from_active_profile(client):
    """The conftest seeds a Books profile with empty prompt strings.
    Update the active profile to carry a real template and verify
    _profile_prompt picks it up."""
    db = SessionLocal()
    try:
        books = db.query(Profile).filter(Profile.slug == "books").one()
        books.prompts = {"hook_system": "PROFILE OVERRIDE"}
        db.commit()
    finally:
        db.close()

    assert (
        llm._profile_prompt("hook_system", "DEFAULT")
        == "PROFILE OVERRIDE"
    )


def test_profile_prompt_renders_jinja_variables(client):
    db = SessionLocal()
    try:
        books = db.query(Profile).filter(Profile.slug == "books").one()
        books.prompts = {
            "hook_system": "Write {{entity}} hooks for {{audience}}."
        }
        db.commit()
    finally:
        db.close()

    # No variables passed to _profile_prompt — so this should fall back
    # to the default (StrictUndefined raises; _profile_prompt catches
    # and returns the default).
    assert (
        llm._profile_prompt("hook_system", "DEFAULT")
        == "DEFAULT"
    )


def test_generate_hooks_dispatches_with_profile_prompt(client):
    """End-to-end: set a known profile prompt, mock dispatch, assert
    the LLM stage actually receives that text."""
    db = SessionLocal()
    try:
        books = db.query(Profile).filter(Profile.slug == "books").one()
        books.prompts = {
            "hook_system": "PROFILE HOOK PROMPT",
            "script_system": "X",
            "scene_prompts_system": "Y",
            "meta_system": "Z",
        }
        db.commit()
    finally:
        db.close()

    captured = {}

    def _fake_dispatch(provider, system, user, tool_name, schema):
        captured[tool_name] = system
        # Minimum shape that makes generate_hooks' post-processing happy.
        return {
            "alternatives": [
                {"angle": "curiosity", "text": "hook1"},
                {"angle": "fear", "text": "hook2"},
                {"angle": "promise", "text": "hook3"},
            ],
            "chosen_index": 0,
            "rationale": "test",
        }

    with patch("app.services.llm.dispatch", side_effect=_fake_dispatch):
        llm.generate_hooks(
            title="X", author="Y", description="Z", genre="fantasy"
        )

    assert captured["record_hooks"] == "PROFILE HOOK PROMPT"
