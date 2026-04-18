from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Series(Base):
    """A grouping of ContentPackages that share a narrative arc or list theme.

    `series_type` drives how the generate endpoint assembles inputs:
      * multipart_book   → one book split across N parts (source_book_id set)
      * author_ranking   → every book by an author (source_author set)
      * themed_list      → curated list of books (use SeriesBook to attach)
      * universe_explainer, recap, monthly_report → free-form
    """

    __tablename__ = "series"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), index=True, unique=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # String value of VideoFormat (e.g. "list", "series_episode").
    format: Mapped[str] = mapped_column(String(32))
    series_type: Mapped[str] = mapped_column(String(32))

    source_content_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_items.id"), nullable=True
    )
    source_author: Mapped[str | None] = mapped_column(String(300), nullable=True)

    total_parts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", server_default="active")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SeriesBook(Base):
    """Join table for series that span multiple books (lists, rankings)."""

    __tablename__ = "series_books"
    __table_args__ = (
        UniqueConstraint("series_id", "position", name="uq_series_books_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id"), index=True)
    content_item_id: Mapped[int] = mapped_column(
        ForeignKey("content_items.id"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
