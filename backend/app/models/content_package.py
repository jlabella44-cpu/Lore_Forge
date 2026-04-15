from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base


class ContentPackage(Base):
    """One row per REVISION. Each regenerate produces a new row.

    Shorts-only posture: single ~150-word script (`script`), 4-5 image prompts,
    narration text, and per-platform meta for the four short-form targets.
    """

    __tablename__ = "content_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1)

    # Script (90-sec target, ~150 words), image prompts, narration
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_prompts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    narration: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Per-platform metadata. Keys: tiktok, yt_shorts, ig_reels, threads
    titles: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hashtags: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Affiliate
    affiliate_amazon: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    affiliate_bookshop: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Regenerate note that produced this revision (null on first)
    regenerate_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
