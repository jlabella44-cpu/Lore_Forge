from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.clock import utc_now
from app.db import Base


class ContentItemSource(Base):
    """Which external source(s) discovered this ContentItem.

    Renamed from BookSource in migration 0010 — rows fan-in multiple
    sources per item (a book on both the NYT list and Goodreads' top of
    the month gets two rows). `source` is the profile-local plugin
    slug (nyt/goodreads/amazon_movers/booktok/reddit_trends for the
    Books profile; rss_feed/manual_input/url_list for any profile).
    """

    __tablename__ = "content_item_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_item_id: Mapped[int] = mapped_column(
        ForeignKey("content_items.id"), index=True
    )
    source: Mapped[str] = mapped_column(String(32))
    score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
