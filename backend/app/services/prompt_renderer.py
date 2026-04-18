"""Jinja2-based prompt templating for profile-driven LLM system prompts.

Phase B4 moves system-prompt strings out of `app/services/prompts/*.py`
and into the active Profile's `prompts` JSON column. The stored values
are Jinja2 templates; callers render them with a variable dict that
encodes profile-specific vocabulary ("book" vs "film", "readers" vs
"viewers", "BookTok" vs "FilmTok", ...).

This module only exposes the rendering primitive + a fetch helper. The
templates themselves live in the DB — see migration 0012 for the seeded
Books values — and callers haven't been routed through this path yet;
that's a follow-up once snapshot tests prove the round-trip is
lossless. For now, `app/services/prompts/short_hook.py` still owns the
canonical hardcoded strings and the LLM service imports from there.

Contract:
  - Unknown variables are rejected (`StrictUndefined`) rather than
    silently rendering empty — catches typos before they reach the LLM.
  - No autoescape: these strings are fed to model APIs, not HTML.
  - Templates are rendered once per request; no caching layer yet.
    Hot-path profiling in Phase 3 can add one if it matters.
"""
from __future__ import annotations

from typing import Any

import jinja2
from sqlalchemy.orm import Session

from app.models.profile import Profile


_ENV = jinja2.Environment(
    undefined=jinja2.StrictUndefined,
    autoescape=False,
    keep_trailing_newline=True,
)


def render(template: str, variables: dict[str, Any] | None = None) -> str:
    """Render a Jinja2 template string with the given variable dict.

    Raises `jinja2.UndefinedError` if the template references a
    variable not in `variables` — by design, so a profile author can't
    accidentally leak `{{entity_type}}` literal into an LLM call.
    """
    return _ENV.from_string(template).render(**(variables or {}))


def get_system_prompt(
    db: Session,
    profile_slug: str,
    stage: str,
    variables: dict[str, Any] | None = None,
) -> str:
    """Load and render one stage's system prompt for a given profile.

    `stage` is one of the keys the active profile declares in its
    `prompts` JSON — typically `hook_system`, `script_system`,
    `scene_prompts_system`, `meta_system` for the short_hook format.

    Raises KeyError when the profile or the stage is missing, rather
    than falling back to a default — callers should handle absence
    explicitly so a mis-configured profile fails loudly.
    """
    profile = db.query(Profile).filter(Profile.slug == profile_slug).one_or_none()
    if profile is None:
        raise KeyError(f"profile {profile_slug!r} not found")
    prompts = profile.prompts or {}
    if stage not in prompts or not prompts[stage]:
        raise KeyError(f"profile {profile_slug!r} has no prompt for stage {stage!r}")
    return render(prompts[stage], variables)
