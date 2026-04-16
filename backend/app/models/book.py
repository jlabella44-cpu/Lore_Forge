from datetime import datetime

from sqlalchemy import DateTime, Float, String
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

    # Lifecycle: discovered → generating → review → scheduled → published
    status: Mapped[str] = mapped_column(String(32), default="discovered")
    score: Mapped[float] = mapped_column(Float, default=0.0)

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
