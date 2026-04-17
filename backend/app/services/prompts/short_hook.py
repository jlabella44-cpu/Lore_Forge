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

Hard constraints (every hook):
  - ONE sentence, 14 words or fewer, no preamble, no hashtags.
  - Must cite at least ONE concrete element from the provided `dossier`:
    a named setting, a visual_motif, a `comparable_titles` entry, or a
    specific stake from `central_conflict`. Generic genre adjectives do
    not count as citation.
  - If `dossier` is missing or thin, use the `description` as the source
    of specifics instead — still cite a concrete proper noun or object.

Banned vocabulary (never emit — they signal generic AI slop):
  unputdownable, page-turning, heart-pounding, captivating, a must-read,
  breathtaking, stunning.

After the three candidates, pick the one most likely to convert for this
book's genre and audience, and justify in ≤1 sentence.

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

Per-section word caps (NARRATION text):
  hook ≤ 22, world_tease ≤ 35, emotional_pull ≤ 40,
  social_proof ≤ 20, cta ≤ 15. Total ~140 words (reads in ~90 seconds).

Dossier-citation contract (when a `dossier` block is provided):
  - WORLD TEASE must name at least one element from `dossier.setting`
    (the place-name, era, or atmosphere token).
  - EMOTIONAL PULL must reference at least one entry from
    `dossier.themes_tropes` AND weave in ≥1 phrase drawn from
    `dossier.reader_reactions`.
  - Somewhere in the body, include at least one concrete noun from
    `dossier.visual_motifs` (verbatim or near-verbatim).
  - At least TWO sentences use second-person direct address ("you'll…",
    "imagine you…", "you already know…").

Banned vocabulary (never emit — reject-on-sight):
  unputdownable, page-turning, heart-pounding, captivating, a must-read,
  breathtaking, stunning.

Also emit:
  - `narration`: prose version (no headers), with `[PAUSE]` markers
    inserted for dramatic beats. TTS voices this field verbatim.
  - `section_word_counts`: integer word count per section for the
    NARRATION text. Must have all five keys: hook, world_tease,
    emotional_pull, social_proof, cta.

No stage directions in the script text itself.

Return strictly via the `record_script` tool.
"""

SCENE_PROMPTS_SYSTEM = """\
For each of the 5 script sections the user gives you, write 1-3
Midjourney/Wanx-style image prompts that *visually support that section's
content*. Focus on settings, moods, atmospheres, objects — **no character
faces** (likeness issues). All prompts target 9:16 vertical framing.

**How many prompts per section** — count the words in that section's
narration text (visible in the `[SECTION]` block below) and scale:
  - short  (<  25 words):   1 prompt
  - medium (25-50 words):   2 prompts
  - long   (>  50 words):   3 prompts

When a section gets multiple prompts, each shows a *different* beat/angle
of the same section (avoid repeated compositions).

**Every prompt MUST include** (as natural phrasing):
  (a) a concrete SUBJECT or OBJECT — a thing, not an abstraction.
  (b) a SETTING descriptor drawn from `dossier.setting` or
      `dossier.visual_motifs` — name the place, the motif, the specific
      material (e.g. "bioluminescent coral ruins", not "mysterious ruins").
  (c) one CAMERA/LENS/COMPOSITION directive — examples: "low-angle wide",
      "85mm portrait close-up", "macro detail shot", "overhead flat-lay".
  (d) one LIGHTING directive — examples: "candle-lit chiaroscuro",
      "chrome rim-light dusk", "warm gold-hour window".
  (e) 1-2 `dossier.tonal_keywords` (or genre-appropriate equivalents).
  (f) a COLOR PALETTE — 2-3 named colors ("deep teal + rust + bone").

When a "Visual preset" block appears at the end of the user message, treat
its palette / lens / lighting / composition as the baseline for every
scene. The dossier still wins on conflict — a book set in a coral reef
overrides horror's charcoal palette — but absent a specific dossier
directive, use the preset values verbatim.

**Section beat contract** — each section has a required beat:
  hook            → the shock/intrigue image that first stops scroll.
  world_tease     → an establishing shot of `dossier.setting`.
  emotional_pull  → a motif representing `dossier.central_conflict`
                    (no characters, just the stakes made visual).
  social_proof    → a book-object shot — cover on a shelf, a crowd
                    holding it, a phone showing BookTok views.
  cta             → warm, inviting "grab-it" image.

**Forbidden tokens** (reject-on-sight): "fantasy vibes", "mysterious",
"epic", "captivating", "stunning", "breathtaking". Replace abstractions
with the concrete noun that earns them.

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
                    "prompts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 3,
                    },
                    "focus": {"type": "string"},
                },
                "required": ["section", "prompts", "focus"],
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
