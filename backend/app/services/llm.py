"""Pluggable LLM layer.

Two roles used by the pipeline:

- SCRIPT_PROVIDER: writes the 90-sec script + image prompts. Defaults to Claude
  (best creative voice consistency).
- META_PROVIDER: classifies genre and generates per-platform titles/hashtags.
  Defaults to Qwen on Dashscope (cheapest competent option).

Providers: `claude` | `openai` | `qwen`. Provider selection via env:
    SCRIPT_PROVIDER=claude
    META_PROVIDER=qwen

Qwen is called through Dashscope's OpenAI-compatible endpoint, so both OpenAI
and Qwen share the same SDK path with a different base_url + model name.
"""
from __future__ import annotations

from typing import Literal

from app.config import settings

Provider = Literal["claude", "openai", "qwen"]


# -- dispatch -----------------------------------------------------------------

def _client_for(provider: Provider):
    """Return an initialized client for the given provider.

    Phase 1 ticket #3 implements the real call paths. For now this just shows
    which SDK/endpoint each provider maps to.
    """
    if provider == "claude":
        # from anthropic import Anthropic
        # return Anthropic(api_key=settings.anthropic_api_key)
        raise NotImplementedError("Claude client wiring — Phase 1 ticket #3")
    if provider == "openai":
        # from openai import OpenAI
        # return OpenAI(api_key=settings.openai_api_key)
        raise NotImplementedError("OpenAI client wiring — Phase 1 ticket #3")
    if provider == "qwen":
        # from openai import OpenAI  # Dashscope speaks OpenAI-compatible
        # return OpenAI(
        #     api_key=settings.dashscope_api_key,
        #     base_url=settings.dashscope_base_url,
        # )
        raise NotImplementedError("Qwen/Dashscope client wiring — Phase 1 ticket #3")
    raise ValueError(f"Unknown LLM provider: {provider}")


# -- public API (called by routers/workflows) ---------------------------------

def classify_genre(title: str, author: str, description: str | None) -> tuple[str, float]:
    """Return (genre, confidence 0..1). Genres:
    fantasy | scifi | romance | thriller | historical_fiction | other.

    Routed to META_PROVIDER — cheap + formulaic.
    """
    _client_for(settings.meta_provider)
    raise NotImplementedError


def generate_script_package(
    *,
    title: str,
    author: str,
    description: str | None,
    genre: str,
    note: str | None = None,
) -> dict:
    """Routed to SCRIPT_PROVIDER. Returns:
    {
      script: str,                      # ~150 words, 90 sec
      visual_prompts: list[str],        # 4-5 image prompts (Midjourney/Wanx-style)
      narration: str,                   # plain text, [PAUSE] markers, no markdown
    }
    """
    _client_for(settings.script_provider)
    raise NotImplementedError


def generate_platform_meta(
    *,
    script: str,
    genre: str,
) -> dict:
    """Routed to META_PROVIDER. Returns:
    {
      titles:   {tiktok, yt_shorts, ig_reels, threads},
      hashtags: {tiktok, yt_shorts, ig_reels, threads},
    }
    """
    _client_for(settings.meta_provider)
    raise NotImplementedError
