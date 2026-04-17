"""Format-keyed prompt registry.

Each VideoFormat maps to a FormatPromptBundle that carries the system prompts,
tool schemas, and generation constants for that format's pipeline stages.

Usage:
    from app.services.prompts import get_bundle
    bundle = get_bundle("list")        # or VideoFormat.LIST
    bundle = get_bundle("short_hook")  # default
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StageSpec:
    """One LLM pipeline stage: system prompt + tool schema + tool name."""

    system: str
    schema: dict[str, Any]
    tool_name: str


@dataclass(frozen=True)
class FormatPromptBundle:
    """Everything a format needs to drive the generation pipeline.

    Any stage can be None if the format skips it (e.g. LIST has no hooks
    stage — the concept is the hook).
    """

    hooks: StageSpec | None
    script: StageSpec
    scene_prompts: StageSpec
    meta: StageSpec

    # Generation constants
    target_duration_sec: int = 90
    scene_count: int = 5
    sections: list[str] = field(default_factory=lambda: [
        "hook", "world_tease", "emotional_pull", "social_proof", "cta",
    ])


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, FormatPromptBundle] = {}


def register(format_key: str, bundle: FormatPromptBundle) -> None:
    _REGISTRY[format_key] = bundle


def get_bundle(format_key: str) -> FormatPromptBundle:
    """Look up a bundle by format string. Raises KeyError if unknown."""
    if format_key not in _REGISTRY:
        raise KeyError(
            f"Unknown video format {format_key!r}. "
            f"Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[format_key]


# Auto-register bundles on import.
from app.services.prompts import short_hook as _sh  # noqa: E402, F401
from app.services.prompts import list_format as _lf  # noqa: E402, F401
