"""Pluggable LLM layer.

Two roles used by the pipeline:

- SCRIPT_PROVIDER: writes the 90-sec script + image prompts + narration.
  Defaults to Claude Opus 4.6 (best creative voice consistency).
- META_PROVIDER: classifies genre and generates per-platform titles/hashtags.
  Defaults to Qwen on Dashscope (cheapest competent option for formulaic work).

Providers: `claude` | `openai` | `qwen`. Selected via env vars
`SCRIPT_PROVIDER` and `META_PROVIDER`.

Claude path uses the official Anthropic SDK with tool-use for structured
output. OpenAI and Qwen paths share the OpenAI SDK — Qwen talks to Dashscope's
OpenAI-compatible endpoint via a different `base_url`.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.config import settings

# ---------------------------------------------------------------------------
# System prompts. Kept stable + deterministic so they can be prompt-cached on
# Claude. No timestamps, UUIDs, or per-request interpolation here.
# ---------------------------------------------------------------------------

_GENRE_SYSTEM = """\
You classify books into one of these genres:
fantasy, scifi, romance, thriller, historical_fiction, other.

Decide based on the title, author, and description alone. Call the
`record_genre` tool exactly once with the chosen genre and a confidence
score between 0.0 and 1.0.
"""

_SCRIPT_SYSTEM = """\
You write spoiler-free 90-second book trailer scripts for short-form social
video (TikTok, YouTube Shorts, Instagram Reels).

Every script follows this five-section arc:

  HOOK            1 punchy sentence. Intrigue, not plot.
  WORLD TEASE     Setting and stakes. No character spoilers.
  EMOTIONAL PULL  Why readers can't put the book down.
  SOCIAL PROOF    One concrete stat: bestseller rank, BookTok views,
                  Goodreads rating, or similar.
  CTA             "Link in bio to grab it." or a close variant.

Tone by genre:
  fantasy, thriller            dark, cinematic, slow dramatic cadence
  scifi                        hype, energetic, fast pace
  romance, historical_fiction  warm, conversational, textured

Constraints:
  - ~150 words total (reads in ~90 seconds).
  - No markdown. No bracketed stage directions in the script text itself.
  - The `narration` field mirrors the spoken words with [PAUSE] markers
    inserted for dramatic beats. TTS reads this field verbatim — do not
    include any other annotations.
  - Produce 4-5 visual prompts targeting 9:16 vertical framing that work in
    Midjourney, Wanx, or DALL-E. No character faces — focus on settings,
    objects, atmospheres, moods.

Output strictly via the `record_package` tool.
"""

_META_SYSTEM = """\
Given a 90-second book trailer script and the book's genre, produce
per-platform titles and hashtags for TikTok, YouTube Shorts, Instagram
Reels, and Threads.

Rules:
  TikTok      title <= 80 chars. 5-8 hashtags. Include #booktok.
  YT Shorts   title <= 100 chars. 5-8 hashtags. Include #shorts and #booktok.
  IG Reels    title <= 100 chars. 5-8 hashtags. Include #bookstagram.
  Threads     a 1-2 line teaser, <= 500 chars total. 3-5 hashtags.

Titles should be punchy and emotional, aligned with the script's hook.
Hashtags should mix niche tags (#fantasybooktok, #darkfantasy) with broader
reach tags (#booktok, #bookrecs).

Output strictly via the `record_meta` tool.
"""

# ---------------------------------------------------------------------------
# JSON schemas shared by the Claude tool path and the OpenAI/Qwen JSON path.
# ---------------------------------------------------------------------------

_GENRE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "genre": {
            "type": "string",
            "enum": [
                "fantasy",
                "scifi",
                "romance",
                "thriller",
                "historical_fiction",
                "other",
            ],
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["genre", "confidence"],
    "additionalProperties": False,
}

_SCRIPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "script": {
            "type": "string",
            "description": "~150 words, five-section arc, no markdown.",
        },
        "visual_prompts": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 4,
            "maxItems": 5,
        },
        "narration": {
            "type": "string",
            "description": "TTS-ready plain text, may include [PAUSE] markers.",
        },
    },
    "required": ["script", "visual_prompts", "narration"],
    "additionalProperties": False,
}

_META_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "titles": {
            "type": "object",
            "properties": {
                "tiktok": {"type": "string"},
                "yt_shorts": {"type": "string"},
                "ig_reels": {"type": "string"},
                "threads": {"type": "string"},
            },
            "required": ["tiktok", "yt_shorts", "ig_reels", "threads"],
            "additionalProperties": False,
        },
        "hashtags": {
            "type": "object",
            "properties": {
                "tiktok": {"type": "array", "items": {"type": "string"}},
                "yt_shorts": {"type": "array", "items": {"type": "string"}},
                "ig_reels": {"type": "array", "items": {"type": "string"}},
                "threads": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tiktok", "yt_shorts", "ig_reels", "threads"],
            "additionalProperties": False,
        },
    },
    "required": ["titles", "hashtags"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Client singletons (lazy — avoids importing SDKs and reading keys at module
# load, which keeps tests and `uvicorn --reload` happy).
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _anthropic_client():
    import anthropic

    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


@lru_cache(maxsize=1)
def _openai_client():
    from openai import OpenAI

    return OpenAI(api_key=settings.openai_api_key)


@lru_cache(maxsize=1)
def _qwen_client():
    # Dashscope exposes an OpenAI-compatible endpoint for Qwen chat models.
    from openai import OpenAI

    return OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )


# ---------------------------------------------------------------------------
# Per-provider call helpers.
# ---------------------------------------------------------------------------

def _claude_call(system: str, user: str, tool_name: str, schema: dict) -> dict:
    """Force Claude to emit one tool_use block with the requested shape."""
    tool = {
        "name": tool_name,
        "description": f"Record the {tool_name.replace('_', ' ')} result.",
        "input_schema": schema,
    }
    resp = _anthropic_client().messages.create(
        model=settings.claude_model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[tool],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            # block.input is a parsed dict from the SDK; copy to detach from
            # the SDK's internal typing.
            return dict(block.input)
    raise RuntimeError("Claude returned no tool_use block")


def _openai_compat_call(
    client, model: str, system: str, user: str, schema: dict
) -> dict:
    """Shared path for OpenAI and Qwen-via-Dashscope."""
    system_with_schema = (
        f"{system}\n\n"
        "Return a single JSON object that strictly matches this schema:\n"
        f"{json.dumps(schema, indent=2)}"
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_with_schema},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
    )
    return json.loads(resp.choices[0].message.content)


def _dispatch(
    role: str,
    system: str,
    user: str,
    tool_name: str,
    schema: dict,
) -> dict:
    """role = 'script' (SCRIPT_PROVIDER) | 'meta' (META_PROVIDER)."""
    provider = settings.script_provider if role == "script" else settings.meta_provider

    if provider == "claude":
        return _claude_call(system, user, tool_name, schema)
    if provider == "openai":
        model = (
            settings.openai_script_model if role == "script" else settings.openai_meta_model
        )
        return _openai_compat_call(_openai_client(), model, system, user, schema)
    if provider == "qwen":
        return _openai_compat_call(_qwen_client(), settings.qwen_model, system, user, schema)
    raise ValueError(f"Unknown LLM provider: {provider!r}")


# ---------------------------------------------------------------------------
# Public API — called from routers and Phase 2 workflows.
# ---------------------------------------------------------------------------

def classify_genre(
    title: str,
    author: str,
    description: str | None,
) -> tuple[str, float]:
    """Return (genre, confidence 0..1).

    Genres: fantasy | scifi | romance | thriller | historical_fiction | other.
    Routes to META_PROVIDER (Qwen by default).
    """
    user = (
        f"Title: {title}\n"
        f"Author: {author}\n"
        f"Description: {description or '(none provided)'}"
    )
    out = _dispatch("meta", _GENRE_SYSTEM, user, "record_genre", _GENRE_SCHEMA)
    return out["genre"], float(out["confidence"])


def generate_script_package(
    *,
    title: str,
    author: str,
    description: str | None,
    genre: str,
    note: str | None = None,
) -> dict:
    """Generate a 90-sec script + 4-5 image prompts + narration.

    Returns: {"script": str, "visual_prompts": list[str], "narration": str}.
    Routes to SCRIPT_PROVIDER (Claude by default).
    """
    lines = [
        f"Book: {title} by {author}",
        f"Genre: {genre}",
        f"Description: {description or '(none provided)'}",
    ]
    if note:
        lines.append(
            "\nRevision note — please address this in the new draft:\n" + note
        )
    user = "\n".join(lines)
    return _dispatch("script", _SCRIPT_SYSTEM, user, "record_package", _SCRIPT_SCHEMA)


def generate_platform_meta(*, script: str, genre: str) -> dict:
    """Generate per-platform titles + hashtags.

    Returns:
        {
            "titles":   {"tiktok", "yt_shorts", "ig_reels", "threads"},
            "hashtags": {"tiktok", "yt_shorts", "ig_reels", "threads"},
        }
    Routes to META_PROVIDER (Qwen by default).
    """
    user = f"Genre: {genre}\n\nScript:\n{script}"
    return _dispatch("meta", _META_SYSTEM, user, "record_meta", _META_SCHEMA)
