from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Analytics(Base):
    """Phase 3. Daily per-video rollup."""

    __tablename__ = "analytics"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    views: Mapped[int] = mapped_column(Integer, default=0)
    watch_time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    affiliate_clicks: Mapped[int] = mapped_column(Integer, default=0)
    revenue_cents: Mapped[float] = mapped_column(Float, default=0.0)
