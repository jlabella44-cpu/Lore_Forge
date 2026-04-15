from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.post("/{package_id}")
def publish(package_id: int) -> dict:
    """Phase 2 — YT long, YT Shorts, TikTok, IG Reels, Threads."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Publishing arrives in Phase 2.",
    )
