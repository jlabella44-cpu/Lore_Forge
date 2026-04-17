"""Delete on-disk renders for never-published packages older than N days.

Unpublished renders pile up fast — each is a 10-15 MB 9:16 mp4 plus five
scene pngs. `prune_stale_renders` walks every rendered package, deletes the
per-package working dir for eligible rows, and clears the `rendered_*`
snapshot columns so the UI no longer shows stale "rendered 42d ago" stats.

Eligibility (all must hold):
  * `package.rendered_at` is set and older than `max_age_days`
  * `book.status != "published"` — live videos stay on disk so the creator
    can re-publish from the same asset. Published + aged is a separate
    concern (archive to cold storage) we're not tackling here.

The function is pure Python — no APScheduler coupling — so it's driven by
an explicit POST /packages/prune-renders, which `routers/generate.py`
wires up. Tests can call it directly with a tiny `max_age_days` to exercise
the eligibility rules deterministically.
"""
from __future__ import annotations

import shutil
from datetime import timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.clock import utc_now
from app.config import settings
from app.models import Book, ContentPackage, ImageAssetCache
from app.observability import log_call


def prune_stale_renders(db: Session, max_age_days: int) -> dict:
    if max_age_days <= 0:
        raise ValueError("max_age_days must be > 0 to prune")

    cutoff = utc_now() - timedelta(days=max_age_days)
    renders_root = Path(settings.renders_dir).resolve()

    eligible = (
        db.query(ContentPackage, Book)
        .join(Book, Book.id == ContentPackage.book_id)
        .filter(
            ContentPackage.rendered_at.is_not(None),
            ContentPackage.rendered_at < cutoff,
            Book.status != "published",
        )
        .all()
    )

    removed: list[int] = []
    freed_bytes = 0
    with log_call(
        "render_retention.prune_stale_renders",
        max_age_days=max_age_days,
        candidates=len(eligible),
    ) as ctx:
        for pkg, _book in eligible:
            work_dir = renders_root / str(pkg.id)
            if work_dir.exists():
                freed_bytes += _dir_size(work_dir)
                shutil.rmtree(work_dir, ignore_errors=True)
            # Always clear the metadata snapshot — even if the dir was
            # already gone (manual rm, different renders_dir, etc.) the
            # UI should stop showing render stats for a deleted mp4.
            pkg.rendered_at = None
            pkg.rendered_duration_seconds = None
            pkg.rendered_size_bytes = None
            pkg.rendered_narration_hash = None
            removed.append(pkg.id)

        db.commit()
        ctx["removed_count"] = len(removed)
        ctx["freed_mb"] = round(freed_bytes / 1_048_576, 2)

    return {
        "removed_count": len(removed),
        "removed_package_ids": removed,
        "freed_bytes": freed_bytes,
        "cutoff_iso": cutoff.isoformat(),
    }


def _dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def prune_stale_image_cache(db: Session, max_age_days: int) -> dict:
    """LRU-prune the image_asset_cache: drop rows whose `last_used_at` is
    older than the cutoff and delete their blobs from disk.

    Unlike `prune_stale_renders`, there's no per-package or publish-status
    coupling — a cache row is just "image N hasn't been needed in X days",
    so the eligibility is pure last_used_at.
    """
    if max_age_days <= 0:
        raise ValueError("max_age_days must be > 0 to prune")

    cutoff = utc_now() - timedelta(days=max_age_days)

    stale = (
        db.query(ImageAssetCache)
        .filter(ImageAssetCache.last_used_at < cutoff)
        .all()
    )

    removed = 0
    freed_bytes = 0
    with log_call(
        "render_retention.prune_stale_image_cache",
        max_age_days=max_age_days,
        candidates=len(stale),
    ) as ctx:
        for row in stale:
            blob = Path(row.file_path)
            if blob.exists():
                try:
                    freed_bytes += blob.stat().st_size
                    blob.unlink()
                except OSError:
                    pass
            db.delete(row)
            removed += 1
        db.commit()
        ctx["removed_count"] = removed
        ctx["freed_mb"] = round(freed_bytes / 1_048_576, 2)

    return {
        "removed_count": removed,
        "freed_bytes": freed_bytes,
        "cutoff_iso": cutoff.isoformat(),
    }
