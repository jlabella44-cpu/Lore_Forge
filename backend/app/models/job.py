from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base


class Job(Base):
    """Async work tracker for long-running operations (generate, render).

    Lifecycle: queued → running → (succeeded | failed). `message` carries a
    short human-readable progress line during the running state so the UI
    can show "Stage 2 of 4 — writing script…" without a dedicated progress
    channel. `result` holds the endpoint's success payload when status
    flips to succeeded; `error` holds the exception detail on failed.
    """

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))  # "generate" | "render"
    target_id: Mapped[int] = mapped_column(Integer, index=True)

    status: Mapped[str] = mapped_column(
        String(32), default="queued", index=True
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
