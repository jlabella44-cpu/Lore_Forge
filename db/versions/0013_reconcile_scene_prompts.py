"""reconcile Books profile scene_prompts_system with llm.py

Revision ID: 0013_reconcile_scene_prompts
Revises: 0012_books_prompts
Create Date: 2026-04-18

Phase B4 follow-up. Migration 0012 seeded Books.prompts from
`app/services/prompts/short_hook.py`, but `app/services/llm.py` owns
the prompt llm actually sends — and its `_SCENE_PROMPTS_SYSTEM` is
slightly more verbose than short_hook.SCENE_PROMPTS_SYSTEM. Routing
llm.py through the profile without first reconciling would produce a
real behavior change (lost wording like "the most distinctive
object/scene from the book", "cozy reading nook, bookstore glow").

This migration overwrites Books.prompts.scene_prompts_system with the
llm.py version so the upcoming caller-routing patch is a zero-diff
refactor. The other three stages (hook/script/meta) already match
llm.py byte-for-byte.

As with 0012, hand-edits are preserved: the migration only overwrites
if the stored text still equals what 0012 seeded.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_reconcile_scene_prompts"
down_revision: Union[str, None] = "0012_books_prompts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The exact text 0012 seeded — copied from
# app/services/prompts/short_hook.py::SCENE_PROMPTS_SYSTEM at the time
# of 0012. Locked here so we can detect operator edits.
_SEEDED_BY_0012 = """\
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

# The canonical version llm.py actually sends.
_LLM_VERSION = """\
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

When a "Visual preset" block appears at the end of the user message, treat
its palette / lens / lighting / composition as the baseline for every
scene. The dossier still wins on conflict — a book set in a coral reef
overrides horror's charcoal palette — but absent a specific dossier
directive, use the preset values verbatim.

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


def upgrade() -> None:
    import json

    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT id, prompts FROM profiles WHERE slug = 'books'")
    ).fetchone()
    if row is None:
        return
    prompts = row.prompts
    if isinstance(prompts, str):
        try:
            prompts = json.loads(prompts)
        except (TypeError, ValueError):
            prompts = {}
    prompts = prompts or {}

    current = prompts.get("scene_prompts_system", "")
    if current != _SEEDED_BY_0012:
        # Operator edited — leave it alone.
        return

    prompts["scene_prompts_system"] = _LLM_VERSION
    conn.execute(
        sa.text(
            "UPDATE profiles SET prompts = :p WHERE id = :i"
        ).bindparams(p=json.dumps(prompts), i=row.id)
    )


def downgrade() -> None:
    import json

    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT id, prompts FROM profiles WHERE slug = 'books'")
    ).fetchone()
    if row is None:
        return
    prompts = row.prompts
    if isinstance(prompts, str):
        try:
            prompts = json.loads(prompts)
        except (TypeError, ValueError):
            prompts = {}
    prompts = prompts or {}
    if prompts.get("scene_prompts_system") == _LLM_VERSION:
        prompts["scene_prompts_system"] = _SEEDED_BY_0012
        conn.execute(
            sa.text(
                "UPDATE profiles SET prompts = :p WHERE id = :i"
            ).bindparams(p=json.dumps(prompts), i=row.id)
        )
