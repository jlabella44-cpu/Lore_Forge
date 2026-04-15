from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Video(Base):
    """Phase 2+. Tracks per-platform uploads of an approved package."""

    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("content_packages.id"))
    platform: Mapped[str] = mapped_column(String(32))  # youtube | yt_shorts | tiktok | ig_reels | threads
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
