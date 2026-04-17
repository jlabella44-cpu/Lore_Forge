from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ImageAssetCache(Base):
    """Content-addressed cache row for a generated image.

    `prompt_hash` is sha256(provider || model || aspect || prompt) so a
    provider or model swap invalidates cleanly. `file_path` points at a
    blob under `{renders_dir}/_cache/images/{hash[:2]}/{hash}.png` that
    survives per-package work_dir deletion.

    `last_used_at` is bumped on every cache hit and drives LRU pruning
    in `render_retention.prune_stale_image_cache`.
    """

    __tablename__ = "image_asset_cache"

    prompt_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    aspect: Mapped[str] = mapped_column(String(8))

    file_path: Mapped[str] = mapped_column(String(1024))
    bytes: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    hit_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
