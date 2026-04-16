from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.clock import utc_now
from app.db import Base


class ContentPackage(Base):
    """One row per REVISION. Each regenerate produces a new row.

    Shorts-only, section-structured pipeline:
      * `script` is stored with `## HOOK`, `## WORLD TEASE`, etc. headers so
        humans and the renderer can split it deterministically.
      * `narration` is the TTS-ready prose version (no headers, [PAUSE] marks).
      * `visual_prompts` is one prompt per script section (5 total), each
        annotated with the section it supports.
      * `hook_alternatives` stashes the three candidates Claude generated so
        future A/B tests can re-draw from them.
      * `captions` is populated at render time from Whisper word-level
        transcription — null until the package has rendered at least once.
      * `rendered_*` columns snapshot the last successful render so the UI
        can show "48s · 12MB · rendered 3h ago" without statting the disk,
        and `rendered_narration_hash` enables stale-render detection when
        the narration text has since been edited.
    """

    __tablename__ = "content_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1)

    # Script + narration.
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    narration: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hook portfolio. `hook_alternatives` = list[{angle, text}], length 3.
    # `chosen_hook_index` points at whichever of those the script used.
    hook_alternatives: Mapped[list | None] = mapped_column(JSON, nullable=True)
    chosen_hook_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Section-anchored image prompts. list[{section, prompt, focus}], length 5.
    visual_prompts: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Per-section narration word counts — used by Remotion to time scenes.
    # {hook: int, world_tease: int, emotional_pull: int, social_proof: int, cta: int}
    section_word_counts: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Populated at render time: list[{word, start, end}] in seconds.
    captions: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Per-platform metadata. Keys: tiktok, yt_shorts, ig_reels, threads
    titles: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hashtags: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Affiliate
    affiliate_amazon: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    affiliate_bookshop: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Regenerate note that produced this revision (null on first)
    regenerate_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)

    # Render snapshot — all null until the first successful render.
    rendered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rendered_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    rendered_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 64-char hex SHA-256 of package.narration at render time. Compared against
    # the current narration's hash to surface "needs re-render" in the UI.
    rendered_narration_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
