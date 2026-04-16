from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.clock import utc_now
from app.db import Base


class BookSource(Base):
    __tablename__ = "book_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    source: Mapped[str] = mapped_column(String(32))  # nyt | goodreads | booktok | amazon | reddit
    score: Mapped[float] = mapped_column(Float, default=0.0)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
