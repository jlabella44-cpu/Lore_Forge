from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.post("/run")
def run_discovery() -> dict:
    """Phase 1: trigger NYT ingest. Phase 2: fan out to all sources."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Discovery not yet implemented (Phase 1 ticket #2).",
    )
