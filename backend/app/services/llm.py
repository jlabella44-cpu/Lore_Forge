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
from app.observability import log_call
from app.services import cost

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

_SCENE_PROMPTS_SYSTEM = """\
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

**Every prompt MUST include** (in any order, as natural phrasing):
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

**Section beat contract** — each section has a required beat:
  hook            → the shock/intrigue image that first stops scroll
                    (the most distinctive object/scene from the book).
  world_tease     → an establishing shot of `dossier.setting`.
  emotional_pull  → a motif representing `dossier.central_conflict`
                    (no characters, just the stakes made visual).
  social_proof    → a book-object shot — the cover on a shelf, a crowd
                    holding it, a phone showing BookTok views.
  cta             → warm, inviting "grab-it" image — cozy reading nook,
                    bookstore glow, hands reaching for the book.

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


_BOOK_DOSSIER_SYSTEM = """\
You build a research dossier about a single book, for downstream short-form
video generation. The dossier is machine-read by other LLM stages to write
hooks, scripts, and image prompts — so it MUST contain concrete, specific,
book-grounded detail, never genre boilerplate.

**Do not invent.** If the user has not given you a fact (a setting name, a
named character arc, a stat), leave that field as an empty string or
empty list. An accurate empty field is infinitely better than a plausible
fabrication.

Emphasis by field:
  - `visual_motifs` (5-8 entries): the most important field. Each entry
    is a concrete noun-phrase with adjectives — the fuel for scene
    prompts. Examples: "a white orchid on black water", "brass compass
    tangled in seaweed", "chrome subway car at midnight". Not
    "mysterious forest", not "beautiful city".
  - `tonal_keywords`: mood words that compound well with imagery
    ("haunting", "bright-neon", "hushed-chapel").
  - `setting`: even if sparse, fill `name`/`era`/`atmosphere` when the
    input supports it. Atmosphere should be adjectival ("humid-gothic",
    "chrome-lit", "sun-bleached").
  - `comparable_titles`: 2-5 well-known works readers compare this to.
    Names only — no commentary.
  - `reader_reactions`: 2-5 short phrases that capture the "feels" TikTok
    readers report ("I couldn't breathe", "the twist ruined me"). No
    verbatim copied reviews — paraphrase.
  - `signature_images`: the book's iconic moments, paraphrased. No
    verbatim copyrighted prose.

Return strictly via the `record_book_dossier` tool.
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

_BOOK_DOSSIER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "setting": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "era": {"type": "string"},
                "atmosphere": {"type": "string"},
            },
            "required": ["name", "era", "atmosphere"],
            "additionalProperties": False,
        },
        "protagonist_sketch": {"type": "string"},
        "central_conflict": {"type": "string"},
        "themes_tropes": {"type": "array", "items": {"type": "string"}},
        "visual_motifs": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 5,
            "maxItems": 8,
        },
        "tonal_keywords": {"type": "array", "items": {"type": "string"}},
        "comparable_titles": {"type": "array", "items": {"type": "string"}},
        "reader_reactions": {"type": "array", "items": {"type": "string"}},
        "content_hooks": {"type": "array", "items": {"type": "string"}},
        "signature_images": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "setting",
        "protagonist_sketch",
        "central_conflict",
        "themes_tropes",
        "visual_motifs",
        "tonal_keywords",
        "comparable_titles",
        "reader_reactions",
        "content_hooks",
        "signature_images",
    ],
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
    try:
        cost.record_llm(
            call_name=f"llm.{tool_name}",
            provider="claude",
            model=settings.claude_model,
            usage=getattr(resp, "usage", None),
        )
    except Exception:
        # Telemetry must never tank the caller.
        pass
    for block in resp.content:
        if block.type == "tool_use":
            return dict(block.input)
    raise RuntimeError("Claude returned no tool_use block")


def _openai_compat_call(
    client, model: str, system: str, user: str, schema: dict, *, provider: str, call_name: str
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
    try:
        cost.record_llm(
            call_name=call_name,
            provider=provider,
            model=model,
            usage=getattr(resp, "usage", None),
        )
    except Exception:
        pass
    return json.loads(resp.choices[0].message.content)


def dispatch(
    role: str,
    system: str,
    user: str,
    tool_name: str,
    schema: dict,
) -> dict:
    """Public LLM dispatch. role: 'script' → SCRIPT_PROVIDER, 'meta' → META_PROVIDER."""
    provider = settings.script_provider if role == "script" else settings.meta_provider
    call_name = f"llm.{tool_name}"

    with log_call(call_name, role=role, provider=provider):
        if provider == "claude":
            return _claude_call(system, user, tool_name, schema)
        if provider == "openai":
            model = (
                settings.openai_script_model
                if role == "script"
                else settings.openai_meta_model
            )
            return _openai_compat_call(
                _openai_client(), model, system, user, schema,
                provider="openai", call_name=call_name,
            )
        if provider == "qwen":
            return _openai_compat_call(
                _qwen_client(), settings.qwen_model, system, user, schema,
                provider="qwen", call_name=call_name,
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
    out = dispatch("meta", system, user, "record_genre", schema)
    return out["genre"], float(out["confidence"])


def _dossier_block(dossier: dict | None) -> str:
    """Format a dossier for inclusion in a user message. Returns "" when
    dossier is None or empty, so callers can safely append unconditionally."""
    if not dossier:
        return ""
    return "\n\nDossier (book-specific research — cite when instructed):\n" + json.dumps(
        dossier, indent=2
    )


def generate_book_dossier(
    *,
    title: str,
    author: str,
    description: str | None,
    scraped_extras: str | None = None,
) -> dict:
    """Stage 0. Build a structured research blob for this book.

    Idempotent when cached upstream (book_research.build_dossier is the
    caller). `scraped_extras` is an optional plain-text dump from
    Firecrawl (Goodreads book page content) that the model may use to
    enrich thin official descriptions.
    """
    lines = [
        f"Title: {title}",
        f"Author: {author}",
        f"Description: {description or '(none provided)'}",
    ]
    if scraped_extras:
        lines.append("")
        lines.append("Supplemental research (Goodreads scrape, trust cautiously):")
        lines.append(scraped_extras[:6000])
    user = "\n".join(lines)
    return dispatch(
        "script",
        _BOOK_DOSSIER_SYSTEM,
        user,
        "record_book_dossier",
        _BOOK_DOSSIER_SCHEMA,
    )


def generate_hooks(
    *,
    title: str,
    author: str,
    description: str | None,
    genre: str,
    dossier: dict | None = None,
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
        f"{_dossier_block(dossier)}"
    )
    out = dispatch("script", _HOOKS_SYSTEM, user, "record_hooks", _HOOKS_SCHEMA)
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
    dossier: dict | None = None,
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
    user = "\n".join(lines) + _dossier_block(dossier)
    return dispatch(
        "script", _SCRIPT_SYSTEM, user, "record_script", _SCRIPT_SCHEMA
    )


def generate_scene_prompts(
    *,
    script: str,
    genre: str,
    dossier: dict | None = None,
) -> dict:
    """Stage 3. Takes the section-headered script from Stage 2 and returns:
        {scenes: [{section, prompts: [str], focus}] × 5}
    """
    sections = script_by_section(script)
    body = "\n\n".join(
        f"[{s.upper()}]\n{sections.get(s, '').strip()}" for s in SECTIONS
    )
    user = f"Genre: {genre}\n\nScript sections:\n{body}{_dossier_block(dossier)}"
    return dispatch(
        "script",
        _SCENE_PROMPTS_SYSTEM,
        user,
        "record_scene_prompts",
        _SCENE_PROMPTS_SCHEMA,
    )


def generate_platform_meta(*, script: str, genre: str) -> dict:
    """Stage 4. Returns {titles: {...}, hashtags: {...}}."""
    user = f"Genre: {genre}\n\nScript:\n{script}"
    return dispatch("meta", _META_SYSTEM, user, "record_meta", _META_SCHEMA)


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
