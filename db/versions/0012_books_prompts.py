"""populate Books profile's prompts JSON with short_hook templates

Revision ID: 0012_books_prompts
Revises: 0011_cta_links
Create Date: 2026-04-18

Phase B4 of the generalization plan. The Books profile's `prompts`
column was seeded as an empty stub in 0009; this migration populates
it with the short_hook format's four system prompts (hook_system,
script_system, scene_prompts_system, meta_system). For now the strings
are copied verbatim from `app/services/prompts/short_hook.py` so the
renderer produces identical output — a later revision can refactor
individual prompts into Jinja2 templates with profile-level variables
once callers are routed through `prompt_renderer.get_system_prompt`.

The strings are inlined rather than imported from the live module so
this migration snapshots the prompts as of this revision. Future
edits to the module won't silently rewrite existing installs'
`prompts` column on re-run.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_books_prompts"
down_revision: Union[str, None] = "0011_cta_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Copy of app/services/prompts/short_hook.py HOOKS_SYSTEM etc. as of
# 2026-04-18. Do NOT import — see module docstring.

_HOOK_SYSTEM = """\
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


def _books_prompts() -> dict:
    return {
        "hook_system": _HOOK_SYSTEM,
        "script_system": _SCRIPT_SYSTEM,
        "scene_prompts_system": _SCENE_PROMPTS_SYSTEM,
        "meta_system": _META_SYSTEM,
    }


def upgrade() -> None:
    conn = op.get_bind()

    # Only overwrite when the column is null-or-empty stubs (matching
    # the seed in 0009). If an operator has hand-edited their Books
    # profile between upgrades, preserve their changes.
    row = conn.execute(
        sa.text("SELECT id, prompts FROM profiles WHERE slug = 'books'")
    ).fetchone()
    if row is None:
        # No Books profile — 0009 should have seeded one, but don't
        # crash the upgrade if an operator removed it.
        return

    existing = row.prompts
    if isinstance(existing, str):
        # Some SQLite builds return JSON columns as raw strings.
        import json

        try:
            existing = json.loads(existing)
        except (TypeError, ValueError):
            existing = {}
    existing = existing or {}

    # Empty strings + missing keys both count as "never filled in".
    has_content = any(existing.get(k) for k in _books_prompts())
    if has_content:
        return

    import json

    conn.execute(
        sa.text(
            "UPDATE profiles SET prompts = :p WHERE id = :i"
        ).bindparams(p=json.dumps(_books_prompts()), i=row.id)
    )


def downgrade() -> None:
    # Reset the Books profile's prompts back to the empty stub 0009
    # seeded. We don't know whether an operator edited them post-0012,
    # so this is best-effort — they'd restore from backup if it
    # matters.
    import json

    conn = op.get_bind()
    stub = {
        "hook_system": "",
        "script_system": "",
        "scene_prompts_system": "",
        "meta_system": "",
    }
    conn.execute(
        sa.text(
            "UPDATE profiles SET prompts = :p WHERE slug = 'books'"
        ).bindparams(p=json.dumps(stub))
    )
