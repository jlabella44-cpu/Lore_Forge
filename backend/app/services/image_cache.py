"""Content-addressed cache for generated images.

The renderer pays real money per image prompt (Wanx ~$0.03, DALL-E 3
~$0.04). A single render issues one call per scene, and a failed or
rerun render re-issues every one of them — unless we remember the
prompt→bytes mapping. This module is that memory.

Key = sha256(provider || model || aspect || prompt), so swapping
IMAGE_PROVIDER or bumping a model invalidates cleanly. The blob lives
at `{renders_dir}/_cache/images/{hash[:2]}/{hash}.png` and a row in
`image_asset_cache` tracks metadata + last_used_at for LRU pruning.

Pruning lives in `render_retention.prune_stale_image_cache`.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from app import db as _db_module  # module attr so tests can swap SessionLocal
from app.clock import utc_now
from app.config import settings
from app.models import ImageAssetCache
from app.observability import get_logger

logger = get_logger("image_cache")


def compute_key(provider: str, model: str, aspect: str, prompt: str) -> str:
    """Hash the inputs that would change the output. Null byte separator
    makes collision-by-concatenation impossible (no valid prompt contains
    \\0)."""
    h = hashlib.sha256()
    h.update(provider.encode("utf-8"))
    h.update(b"\0")
    h.update(model.encode("utf-8"))
    h.update(b"\0")
    h.update(aspect.encode("utf-8"))
    h.update(b"\0")
    h.update((prompt or "").encode("utf-8"))
    return h.hexdigest()


def cache_root() -> Path:
    return Path(settings.renders_dir).resolve() / "_cache" / "images"


def _blob_path(key: str) -> Path:
    return cache_root() / key[:2] / f"{key}.png"


def get_or_generate(
    *,
    prompt: str,
    out_path: Path,
    provider: str,
    model: str,
    aspect: str,
    produce: Callable[[Path], None],
) -> bool:
    """Return True on cache hit, False on miss (provider was called).

    On hit: copy the cached blob to `out_path` and bump last_used_at.
    On miss: call `produce(out_path)` to write fresh bytes, then copy
    those bytes into the cache for next time.

    Disabled entirely when `settings.image_cache_enabled` is False —
    callers should treat that path as equivalent to "always miss".
    """
    if not settings.image_cache_enabled:
        produce(out_path)
        return False

    key = compute_key(provider, model, aspect, prompt)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    db: Session = _db_module.SessionLocal()
    try:
        row = db.get(ImageAssetCache, key)
        if row is not None and Path(row.file_path).exists():
            shutil.copyfile(row.file_path, out_path)
            row.last_used_at = utc_now()
            row.hit_count = (row.hit_count or 0) + 1
            db.commit()
            logger.info(
                "image_cache.hit key=%s provider=%s hits=%d",
                key[:12],
                provider,
                row.hit_count,
            )
            return True

        # Miss — either no row, or row exists but blob was deleted on
        # disk. In the stale-row case we'll overwrite it below.
        produce(out_path)
        _store(db, key, provider, model, aspect, out_path, existing=row)
        return False
    finally:
        db.close()


def _store(
    db: Session,
    key: str,
    provider: str,
    model: str,
    aspect: str,
    src: Path,
    *,
    existing: ImageAssetCache | None,
) -> None:
    blob = _blob_path(key)
    blob.parent.mkdir(parents=True, exist_ok=True)
    # copyfile, not move — the caller still needs the file at out_path
    # to feed Remotion in the same render.
    shutil.copyfile(src, blob)
    size = blob.stat().st_size
    now = utc_now()

    if existing is None:
        db.add(
            ImageAssetCache(
                prompt_hash=key,
                provider=provider,
                model=model,
                aspect=aspect,
                file_path=str(blob),
                bytes=size,
                created_at=now,
                last_used_at=now,
                hit_count=0,
            )
        )
    else:
        existing.provider = provider
        existing.model = model
        existing.aspect = aspect
        existing.file_path = str(blob)
        existing.bytes = size
        existing.created_at = now
        existing.last_used_at = now
        existing.hit_count = 0
    db.commit()
    logger.info(
        "image_cache.store key=%s provider=%s bytes=%d",
        key[:12],
        provider,
        size,
    )
