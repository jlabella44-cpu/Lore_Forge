from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("")
def analytics_summary() -> dict:
    """Phase 3 — views, affiliate clicks, revenue rollups."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Analytics arrives in Phase 3.",
    )
