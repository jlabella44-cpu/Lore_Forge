from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CostRecord(Base):
    """One row per external API call we paid for.

    `estimated_cents` is the per-row cost our pricing table derived from
    the call's usage. Always populated — unknown (provider, model) pairs
    record 0 and log a warning rather than failing the call.

    `package_id` is nullable so classify-only discovery calls, which fire
    before a ContentPackage exists, still get recorded (for the global
    30-day rollup).
    """

    __tablename__ = "cost_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    call_name: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # For non-token providers: 1 image, N seconds, N characters.
    units: Mapped[float | None] = mapped_column(Float, nullable=True)

    estimated_cents: Mapped[float] = mapped_column(Float, default=0.0)

    package_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_packages.id"), nullable=True, index=True
    )
