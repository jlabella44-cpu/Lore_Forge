from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.post("/books/{book_id}/generate")
def generate_package(book_id: int, payload: dict | None = None) -> dict:
    """Phase 1 ticket #3 — call Claude, persist a new ContentPackage revision."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Generation not yet implemented (Phase 1 ticket #3).",
    )


@router.post("/packages/{package_id}/approve")
def approve_package(package_id: int) -> dict:
    """Mark a specific revision as the approved one for its book."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Approve not yet implemented (Phase 1 ticket #5).",
    )
