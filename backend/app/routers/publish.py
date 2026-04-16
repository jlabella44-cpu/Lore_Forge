"""Publish an approved + rendered package to a social platform.

Manual Approve + manual Render gate every upload. Each successful upload
creates a `videos` row; each failed upload surfaces the provider error
verbatim so the user can see exactly why (common in OAuth / app-review land).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.db import get_db
from app.models import Book, ContentPackage, Video
from app.services import meta as meta_svc
from app.services import tiktok as tiktok_svc
from app.services import youtube as yt_svc

router = APIRouter()

# Supported platforms map to a human-friendly label for the UI + error text.
SUPPORTED_PLATFORMS = {
    "yt_shorts": "YouTube Shorts",
    "tiktok": "TikTok",
    "ig_reels": "Instagram Reels",
    "threads": "Threads",
}


@router.post("/{package_id}/{platform}")
def publish_package(
    package_id: int,
    platform: str,
    db: Session = Depends(get_db),
) -> dict:
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown platform {platform!r}. "
                f"Supported: {', '.join(SUPPORTED_PLATFORMS)}"
            ),
        )

    package = db.get(ContentPackage, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found")
    if not package.is_approved:
        raise HTTPException(
            status_code=400, detail="Package must be approved before publishing"
        )

    book = db.get(Book, package.book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    mp4_path = _expected_mp4_path(package_id)
    if not mp4_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"No rendered video found. Render the package first. (looked at {mp4_path})",
        )

    titles = package.titles or {}
    hashtags = package.hashtags or {}
    title = titles.get(platform, book.title)
    tag_list = hashtags.get(platform, [])

    try:
        external_id = _dispatch_upload(
            platform=platform,
            mp4_path=mp4_path,
            title=title,
            hashtags=tag_list,
            affiliate_amazon=package.affiliate_amazon,
            affiliate_bookshop=package.affiliate_bookshop,
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    video = Video(
        book_id=book.id,
        package_id=package.id,
        platform=platform,
        file_path=str(mp4_path),
        external_id=external_id,
        published_at=utc_now(),
    )
    db.add(video)

    # Final lifecycle state for this book.
    book.status = "published"

    db.commit()
    db.refresh(video)
    return {
        "video_id": video.id,
        "platform": platform,
        "external_id": external_id,
        "published_at": video.published_at.isoformat(),
    }


# ---------------------------------------------------------------------------


def _expected_mp4_path(package_id: int) -> Path:
    """Renderer writes to `{renders_dir}/{package_id}/out.mp4` — see
    services/renderer.py. Keeping this derivation local avoids coupling the
    publish router to the renderer's internals."""
    from app.config import settings

    return Path(settings.renders_dir).resolve() / str(package_id) / "out.mp4"


def _build_description(
    title: str,
    hashtags: list[str],
    affiliate_amazon: str | None,
    affiliate_bookshop: str | None,
) -> str:
    """Build a platform-generic description with affiliate links appended."""
    parts = [title]
    links = []
    if affiliate_amazon:
        links.append(f"Amazon: {affiliate_amazon}")
    if affiliate_bookshop:
        links.append(f"Bookshop.org: {affiliate_bookshop}")
    if links:
        parts.append("")
        parts.extend(links)
    if hashtags:
        parts.append("")
        parts.append(" ".join(hashtags))
    return "\n".join(parts)


def _dispatch_upload(
    *,
    platform: str,
    mp4_path: Path,
    title: str,
    hashtags: list[str],
    affiliate_amazon: str | None,
    affiliate_bookshop: str | None,
) -> str:
    """Route to the right service module. Returns the platform's video ID."""
    description = _build_description(title, hashtags, affiliate_amazon, affiliate_bookshop)

    if platform == "yt_shorts":
        return yt_svc.upload(
            mp4_path,
            title=title,
            description=description,
            tags=hashtags,
        )
    if platform == "tiktok":
        return tiktok_svc.upload(
            mp4_path,
            caption=title,
            hashtags=hashtags,
        )
    if platform == "ig_reels":
        # Meta fetches from a URL, not a local path — Phase 3 work: stand up
        # a signed, short-lived upload bucket or reuse the FastAPI static
        # /renders mount if deployed publicly.
        video_url = _public_url_for(mp4_path)
        return meta_svc.upload_reels(
            video_url,
            caption=title,
            hashtags=hashtags,
        )
    if platform == "threads":
        video_url = _public_url_for(mp4_path)
        return meta_svc.upload_threads(
            video_url,
            text=title,
            hashtags=hashtags,
        )
    raise RuntimeError(f"No dispatcher for platform {platform!r}")


def _public_url_for(mp4_path: Path) -> str:
    """IG Reels + Threads require a publicly reachable URL, not a local path.
    Phase 2 leaves this raising so the UI shows a clear error; Phase 3 wires
    a tunnel (ngrok / Cloudflare Tunnel) or S3 signed URLs."""
    raise NotImplementedError(
        "Meta platforms (Instagram Reels, Threads) require a public video URL. "
        "Wire a tunnel or a signed-URL bucket before enabling these targets."
    )
