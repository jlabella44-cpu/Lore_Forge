from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.clock import utc_now
from app.db import Base


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[str] = mapped_column(String(300))
    isbn: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    asin: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)

    # Genre: Claude proposes, user can override.
    genre: Mapped[str | None] = mapped_column(String(64), nullable=True)
    genre_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    genre_override: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Lifecycle: discovered → generating → review → scheduled → rendered → published
    # Plus terminal side-states: `skipped` (hidden from the default queue).
    # Transitions:
    #   discover:         (new) → discovered
    #   generate start:   discovered|review → generating
    #   generate done:    generating → review (or revert to previous on failure)
    #   approve package:  review → scheduled
    #   render success:   scheduled → rendered  (no-op on published or other states)
    #   publish success:  rendered → published
    status: Mapped[str] = mapped_column(
        String(32), default="discovered", server_default="discovered"
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")

    # Structured research blob — setting, protagonist sketch, visual_motifs,
    # tonal_keywords, comparable_titles, reader_reactions, etc. Built once per
    # book on first generate and reused by every downstream creative stage so
    # hooks and scene prompts cite book-specific details instead of genre mush.
    dossier: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
