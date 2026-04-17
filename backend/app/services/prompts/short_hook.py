"""SHORT_HOOK format — the original 60-90s single-book teaser.

Prompts and schemas extracted from llm.py. The originals in llm.py stay
as-is for backward compatibility; this module is the canonical source for
the format registry.
"""
from __future__ import annotations

from app.services.prompts import FormatPromptBundle, StageSpec, register

SECTIONS = ["hook", "world_tease", "emotional_pull", "social_proof", "cta"]

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

HOOKS_SYSTEM = """\
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

SCRIPT_SYSTEM = """\
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

SCENE_PROMPTS_SYSTEM = """\
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

META_SYSTEM = """\
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
# Schemas
# ---------------------------------------------------------------------------

HOOK_ANGLES = ["curiosity", "fear", "promise"]

HOOKS_SCHEMA = {
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

SCRIPT_SCHEMA = {
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

SCENE_PROMPTS_SCHEMA = {
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

META_SCHEMA = {
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
# Bundle
# ---------------------------------------------------------------------------

SHORT_HOOK_BUNDLE = FormatPromptBundle(
    hooks=StageSpec(
        system=HOOKS_SYSTEM,
        schema=HOOKS_SCHEMA,
        tool_name="record_hooks",
    ),
    script=StageSpec(
        system=SCRIPT_SYSTEM,
        schema=SCRIPT_SCHEMA,
        tool_name="record_script",
    ),
    scene_prompts=StageSpec(
        system=SCENE_PROMPTS_SYSTEM,
        schema=SCENE_PROMPTS_SCHEMA,
        tool_name="record_scene_prompts",
    ),
    meta=StageSpec(
        system=META_SYSTEM,
        schema=META_SCHEMA,
        tool_name="record_meta",
    ),
    target_duration_sec=90,
    scene_count=5,
    sections=SECTIONS,
)

register("short_hook", SHORT_HOOK_BUNDLE)
