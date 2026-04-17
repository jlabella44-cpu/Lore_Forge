"""LIST format — "Top N books for X" style compilation video.

Input is a list of books, not a single book. The script structure is:
intro → N book mini-pitches (20-30s each) → CTA. Scene prompts are
one per book (cover-style or thematic), not per-section.

Hooks stage is None — the list concept IS the hook ("Top 10 Fantasy
Books for Game of Thrones Fans").
"""
from __future__ import annotations

from app.services.prompts import FormatPromptBundle, StageSpec, register

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

SCRIPT_SYSTEM = """\
You write short-form video scripts for "Top N Books" list videos on TikTok,
YouTube Shorts, Instagram Reels.

The user gives you a list title (e.g. "Top 10 Fantasy Books for GoT Fans")
and N books with their descriptions AND per-book `dossier` blocks. Write
a script structured as:

  ## INTRO
  One punchy sentence that IS the hook — the list title rephrased as a
  scroll-stopping question or promise. Under 15 words.

  ## BOOK 1: {Title}
  ## BOOK 2: {Title}
  ... (one section per book)
  Each book section: 2-3 sentences. Spoiler-free pitch — what makes THIS
  book belong on THIS list. **Cite at least one concrete detail from the
  book's dossier** (a visual_motif, a setting name, a comparable title,
  or a reader_reaction). End with a one-line emotional kicker.

  ## CTA
  "Links in bio for every book on this list." or similar.

Tone: energetic, authoritative, like a trusted friend who reads everything.

Banned vocabulary (never emit): unputdownable, page-turning, heart-pounding,
captivating, a must-read, breathtaking, stunning.

Also emit:
  - `narration`: prose version (no headers), with [PAUSE] between books.
  - `book_word_counts`: list of {title, words} with the narration word count
    per book section. Include intro and cta as entries too.

Return strictly via the `record_list_script` tool.
"""

SCENE_PROMPTS_SYSTEM = """\
For each book in a "Top N" list video, write 1-2 Midjourney/Wanx-style
image prompts that evoke THAT book's specific world. Focus on settings,
atmospheres, symbolic objects — **no character faces**.

Use 1 prompt for most books. Use 2 prompts when a book's narration runs
long (>40 words) so the screen doesn't linger on a single image.

Each prompt MUST cite a concrete element from that book's dossier —
ideally a `visual_motifs` entry or the `setting.name`. Include a
camera/lens directive, a lighting directive, 1-2 `tonal_keywords`,
and a 2-3 color palette. All prompts target 9:16 vertical framing.

Each prompt should feel distinct so the video has visual variety across
the list. Forbidden: "fantasy vibes", "mysterious", "epic", "captivating".

Also include an `intro` scene (atmospheric, genre-spanning) and a `cta`
scene (warm, inviting, books-on-shelf aesthetic) — each with 1 prompt.

Return via the `record_list_scene_prompts` tool.
"""

META_SYSTEM = """\
Given a "Top N Books" list video script, produce per-platform titles and
hashtags for TikTok, YouTube Shorts, Instagram Reels, and Threads.

Rules:
  TikTok      title <= 80 chars.  5-8 hashtags. Include #booktok.
  YT Shorts   title <= 100 chars. 5-8 hashtags. Include #shorts and #booktok.
  IG Reels    title <= 100 chars. 5-8 hashtags. Include #bookstagram.
  Threads     a 1-2 line teaser, <= 500 chars. 3-5 hashtags.

The title should feature the list concept prominently. Hashtags mix the
list's genre niche with broad reach tags.

Return strictly via the `record_meta` tool.
"""

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "script": {
            "type": "string",
            "description": "Full script with ## INTRO, ## BOOK 1: Title, ..., ## CTA headers.",
        },
        "narration": {
            "type": "string",
            "description": "TTS-ready prose. No headers; [PAUSE] between books.",
        },
        "book_word_counts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "words": {"type": "integer", "minimum": 0},
                },
                "required": ["title", "words"],
            },
        },
    },
    "required": ["script", "narration", "book_word_counts"],
    "additionalProperties": False,
}

SCENE_PROMPTS_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "'intro', 'cta', or the book title",
                    },
                    "prompts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 3,
                    },
                    "focus": {"type": "string"},
                },
                "required": ["label", "prompts", "focus"],
            },
        },
    },
    "required": ["scenes"],
    "additionalProperties": False,
}

# Reuse the standard meta schema from short_hook.
from app.services.prompts.short_hook import META_SCHEMA

# ---------------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------------

LIST_BUNDLE = FormatPromptBundle(
    hooks=None,  # List concept IS the hook — no separate hooks stage.
    script=StageSpec(
        system=SCRIPT_SYSTEM,
        schema=SCRIPT_SCHEMA,
        tool_name="record_list_script",
    ),
    scene_prompts=StageSpec(
        system=SCENE_PROMPTS_SYSTEM,
        schema=SCENE_PROMPTS_SCHEMA,
        tool_name="record_list_scene_prompts",
    ),
    meta=StageSpec(
        system=META_SYSTEM,
        schema=META_SCHEMA,
        tool_name="record_meta",
    ),
    target_duration_sec=0,  # Variable — depends on N books × ~25s each.
    scene_count=0,          # Variable — N books + intro + cta.
    sections=[],            # Not section-based; scenes keyed by book title.
)

register("list", LIST_BUNDLE)
