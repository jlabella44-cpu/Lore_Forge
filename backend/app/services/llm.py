"""Pluggable LLM layer.

Four functions drive the staged generation pipeline. The routing concept is
unchanged from Phase 1: SCRIPT_PROVIDER (default Claude) handles quality-
sensitive creative work; META_PROVIDER (default Qwen on Dashscope) handles
cheap, formulaic tasks.

    generate_hooks(...)         → SCRIPT_PROVIDER  (3 hook candidates + pick)
    generate_script(...)        → SCRIPT_PROVIDER  (script + narration)
    generate_scene_prompts(...) → SCRIPT_PROVIDER  (5 section-anchored prompts)
    generate_platform_meta(...) → META_PROVIDER    (titles + hashtags)

Sections are the canonical vocabulary used across the schema, the script
headers, the image prompts, and the Remotion template:
    hook, world_tease, emotional_pull, social_proof, cta
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.config import settings

SECTIONS: list[str] = [
    "hook",
    "world_tease",
    "emotional_pull",
    "social_proof",
    "cta",
]

# Markdown header emitted for each section in the `script` field.
SECTION_HEADERS: dict[str, str] = {
    "hook": "## HOOK",
    "world_tease": "## WORLD TEASE",
    "emotional_pull": "## EMOTIONAL PULL",
    "social_proof": "## SOCIAL PROOF",
    "cta": "## CTA",
}

HOOK_ANGLES: list[str] = ["curiosity", "fear", "promise"]

# ---------------------------------------------------------------------------
# System prompts — stable strings so Claude's prompt cache can pick them up.
# ---------------------------------------------------------------------------

_HOOKS_SYSTEM = """\
You write single-sentence TikTok/Shorts hooks for book trailer videos.

A great hook stops the scroll in under 0.8 seconds. Generate exactly three
candidates, each using a *different* emotional angle:

  curiosity   — a specific unresolved question the book answers
  fear        — a visceral stake or dread the book taps into
  promise     — an "if you loved X you'll love this" identification line

Each hook must be ONE sentence, under 20 words, no preamble, no hashtags.
Then pick the one you think will perform best for this book's genre and
audience, and explain why in at most one sentence.

Return strictly via the `record_hooks` tool.
"""

_SCRIPT_SYSTEM = """\
You write spoiler-free 90-second book trailer scripts for short-form social
video (TikTok, YouTube Shorts, Instagram Reels).

Use the HOOK I give you **verbatim** as the first line of the script, under
a `## HOOK` header. Then structure the rest of the script in four more
sections, each with a markdown header:

  ## WORLD TEASE       — Setting + stakes. No character spoilers.
  ## EMOTIONAL PULL    — Why readers can't put the book down.
  ## SOCIAL PROOF      — ONE concrete stat: bestseller rank, BookTok views,
                         Goodreads rating, or similar.
  ## CTA               — "Link in bio to grab it." or a close variant.

Tone by genre:
  fantasy, thriller             dark, cinematic, slow dramatic cadence
  scifi                         hype, energetic, fast pace
  romance, historical_fiction   warm, conversational, textured

Constraints:
  - ~150 words total across all five sections (reads in ~90 seconds).
  - No stage directions in the script text itself.
  - Also emit `narration`: the same content as prose (no headers), with
    `[PAUSE]` markers inserted for dramatic beats. TTS voices this field
    verbatim.
  - Also emit `section_word_counts`: an integer word count per section for
    the NARRATION text. Must have all five keys: hook, world_tease,
    emotional_pull, social_proof, cta.

Return strictly via the `record_script` tool.
"""

_SCENE_PROMPTS_SYSTEM = """\
For each of the 5 script sections the user gives you, write one
Midjourney/Wanx-style image prompt that *visually supports that section's
content*. Focus on settings, moods, atmospheres, objects — **no character
faces** (likeness issues). All prompts target 9:16 vertical framing.

Also attach a short `focus` label per scene describing what the image needs
to communicate (e.g. "stakes of the world", "emotional climax tease",
"social proof: bestseller list").

Return exactly 5 scenes, in this section order:
  1. hook
  2. world_tease
  3. emotional_pull
  4. social_proof
  5. cta

Return strictly via the `record_scene_prompts` tool.
"""

_META_SYSTEM = """\
Given a 90-second book trailer script and the book's genre, produce
per-platform titles and hashtags for TikTok, YouTube Shorts, Instagram
Reels, and Threads.

Rules:
  TikTok      title <= 80 chars.  5-8 hashtags. Include #booktok.
  YT Shorts   title <= 100 chars. 5-8 hashtags. Include #shorts and #booktok.
  IG Reels    title <= 100 chars. 5-8 hashtags. Include #bookstagram.
  Threads     a 1-2 line teaser, <= 500 chars. 3-5 hashtags.

Titles should be punchy and emotional, aligned with the script's hook.
Hashtags mix niche (#fantasybooktok, #darkfantasy) with broader reach
(#booktok, #bookrecs).

Return strictly via the `record_meta` tool.
"""

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

_HOOKS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "alternatives": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "angle": {"type": "string", "enum": HOOK_ANGLES},
                    "text": {"type": "string"},
                },
                "required": ["angle", "text"],
            },
        },
        "chosen_index": {"type": "integer", "minimum": 0, "maximum": 2},
        "rationale": {"type": "string"},
    },
    "required": ["alternatives", "chosen_index", "rationale"],
    "additionalProperties": False,
}

_SCRIPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "script": {
            "type": "string",
            "description": "Full script with `## HOOK`, `## WORLD TEASE`, ... headers.",
        },
        "narration": {
            "type": "string",
            "description": "TTS-ready prose. No markdown headers; may contain [PAUSE] marks.",
        },
        "section_word_counts": {
            "type": "object",
            "properties": {s: {"type": "integer", "minimum": 0} for s in SECTIONS},
            "required": SECTIONS,
            "additionalProperties": False,
        },
    },
    "required": ["script", "narration", "section_word_counts"],
    "additionalProperties": False,
}

_SCENE_PROMPTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string", "enum": SECTIONS},
                    "prompt": {"type": "string"},
                    "focus": {"type": "string"},
                },
                "required": ["section", "prompt", "focus"],
            },
        },
    },
    "required": ["scenes"],
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
# Clients
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
    from openai import OpenAI

    return OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )


# ---------------------------------------------------------------------------
# Per-provider call helpers
# ---------------------------------------------------------------------------

def _claude_call(system: str, user: str, tool_name: str, schema: dict) -> dict:
    tool = {
        "name": tool_name,
        "description": f"Record the {tool_name.replace('_', ' ')} result.",
        "input_schema": schema,
    }
    resp = _anthropic_client().messages.create(
        model=settings.claude_model,
        max_tokens=4096,
        system=[
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ],
        tools=[tool],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return dict(block.input)
    raise RuntimeError("Claude returned no tool_use block")


def _openai_compat_call(
    client, model: str, system: str, user: str, schema: dict
) -> dict:
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
    """role: 'script' → SCRIPT_PROVIDER, 'meta' → META_PROVIDER."""
    provider = settings.script_provider if role == "script" else settings.meta_provider

    if provider == "claude":
        return _claude_call(system, user, tool_name, schema)
    if provider == "openai":
        model = (
            settings.openai_script_model
            if role == "script"
            else settings.openai_meta_model
        )
        return _openai_compat_call(_openai_client(), model, system, user, schema)
    if provider == "qwen":
        return _openai_compat_call(
            _qwen_client(), settings.qwen_model, system, user, schema
        )
    raise ValueError(f"Unknown LLM provider: {provider!r}")


# ---------------------------------------------------------------------------
# Public API — Phase 2+ staged chain
# ---------------------------------------------------------------------------

def classify_genre(
    title: str, author: str, description: str | None
) -> tuple[str, float]:
    """Classify a book into one of our six genres. Routes to META_PROVIDER."""
    schema = {
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
    system = (
        "You classify books into one of these genres:\n"
        "fantasy, scifi, romance, thriller, historical_fiction, other.\n"
        "Decide based on the title, author, and description alone. "
        "Call the `record_genre` tool exactly once."
    )
    user = (
        f"Title: {title}\n"
        f"Author: {author}\n"
        f"Description: {description or '(none provided)'}"
    )
    out = _dispatch("meta", system, user, "record_genre", schema)
    return out["genre"], float(out["confidence"])


def generate_hooks(
    *,
    title: str,
    author: str,
    description: str | None,
    genre: str,
) -> dict:
    """Stage 1. Returns:
        {alternatives: [{angle, text}] * 3, chosen_index: int, rationale: str}
    Routes to SCRIPT_PROVIDER (Claude by default — hook quality is the
    whole game).
    """
    user = (
        f"Book: {title} by {author}\n"
        f"Genre: {genre}\n"
        f"Description: {description or '(none provided)'}"
    )
    out = _dispatch("script", _HOOKS_SYSTEM, user, "record_hooks", _HOOKS_SCHEMA)
    # Clamp the index in case the model hallucinates past the array length.
    out["chosen_index"] = max(0, min(2, int(out["chosen_index"])))
    return out


def generate_script(
    *,
    title: str,
    author: str,
    description: str | None,
    genre: str,
    chosen_hook: str,
    note: str | None = None,
) -> dict:
    """Stage 2. Returns:
        {script: str (with markdown headers), narration: str,
         section_word_counts: {hook, world_tease, emotional_pull, social_proof, cta}}
    """
    lines = [
        f"Book: {title} by {author}",
        f"Genre: {genre}",
        f"Description: {description or '(none provided)'}",
        "",
        f"HOOK (use verbatim as the first line of the script): {chosen_hook}",
    ]
    if note:
        lines.append("")
        lines.append(
            "Revision note — please address this in the new draft:\n" + note
        )
    user = "\n".join(lines)
    return _dispatch(
        "script", _SCRIPT_SYSTEM, user, "record_script", _SCRIPT_SCHEMA
    )


def generate_scene_prompts(
    *,
    script: str,
    genre: str,
) -> dict:
    """Stage 3. Takes the section-headered script from Stage 2 and returns:
        {scenes: [{section, prompt, focus}] × 5}
    """
    sections = script_by_section(script)
    body = "\n\n".join(
        f"[{s.upper()}]\n{sections.get(s, '').strip()}" for s in SECTIONS
    )
    user = f"Genre: {genre}\n\nScript sections:\n{body}"
    return _dispatch(
        "script",
        _SCENE_PROMPTS_SYSTEM,
        user,
        "record_scene_prompts",
        _SCENE_PROMPTS_SCHEMA,
    )


def generate_platform_meta(*, script: str, genre: str) -> dict:
    """Stage 4. Returns {titles: {...}, hashtags: {...}}."""
    user = f"Genre: {genre}\n\nScript:\n{script}"
    return _dispatch("meta", _META_SYSTEM, user, "record_meta", _META_SCHEMA)


# ---------------------------------------------------------------------------
# Script parsing
# ---------------------------------------------------------------------------

def script_by_section(script: str) -> dict[str, str]:
    """Split a section-headered script into a dict keyed by section name.

    Lenient about header casing and extra whitespace. Missing sections
    return empty strings so downstream code can assume all five keys exist.
    """
    out = {s: "" for s in SECTIONS}
    if not script:
        return out

    # Build a reverse lookup from normalized header text → section name
    norm_to_section = {
        _normalize_header(h): s for s, h in SECTION_HEADERS.items()
    }

    current: str | None = None
    buf: list[str] = []
    for line in script.splitlines():
        stripped = line.strip()
        norm = _normalize_header(stripped)
        if norm in norm_to_section:
            if current is not None:
                out[current] = "\n".join(buf).strip()
            current = norm_to_section[norm]
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf).strip()

    return out


def _normalize_header(s: str) -> str:
    # "## HOOK" → "hook"; tolerant to `# HOOK`, `### Hook`, `## Hook:` etc.
    s = s.strip().lstrip("#").strip().rstrip(":").strip().lower()
    return s
