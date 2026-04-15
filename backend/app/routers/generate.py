"""Content package generation + approval."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Book, ContentPackage
from app.services import amazon, llm, renderer

router = APIRouter()


@router.post("/books/{book_id}/generate")
def generate_package(
    book_id: int,
    payload: dict | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Create a new ContentPackage revision. Body may be `{"note": "..."}`
    to steer a regenerate."""
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    note = (payload or {}).get("note")
    genre = book.genre_override or book.genre or "other"

    previous_status = book.status
    book.status = "generating"
    db.commit()

    try:
        script_pkg = llm.generate_script_package(
            title=book.title,
            author=book.author,
            description=book.description,
            genre=genre,
            note=note,
        )
        meta = llm.generate_platform_meta(script=script_pkg["script"], genre=genre)
        affiliate_amazon, affiliate_bookshop = _affiliate_links(book.isbn)

        last_revision = (
            db.query(func.max(ContentPackage.revision_number))
            .filter(ContentPackage.book_id == book_id)
            .scalar()
            or 0
        )
        package = ContentPackage(
            book_id=book_id,
            revision_number=last_revision + 1,
            script=script_pkg["script"],
            visual_prompts=script_pkg["visual_prompts"],
            narration=script_pkg["narration"],
            titles=meta["titles"],
            hashtags=meta["hashtags"],
            affiliate_amazon=affiliate_amazon,
            affiliate_bookshop=affiliate_bookshop,
            regenerate_note=note,
            is_approved=False,
        )
        db.add(package)
        book.status = "review"
        db.commit()
        db.refresh(package)
        return {"package_id": package.id, "revision_number": package.revision_number}

    except Exception as exc:
        db.rollback()
        # Re-read book in a fresh txn and restore the prior status
        book = db.get(Book, book_id)
        if book is not None:
            book.status = previous_status
            db.commit()
        raise HTTPException(status_code=502, detail=f"Generation failed: {exc}") from exc


@router.post("/packages/{package_id}/render")
def render_package(
    package_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Kick off the full render pipeline for an approved package.

    Synchronous for Phase 2 — renders take ~1-3 minutes. If this turns into
    a UX problem the call chain is small enough to move into a FastAPI
    BackgroundTask without restructuring.
    """
    package = db.get(ContentPackage, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found")
    if not package.is_approved:
        raise HTTPException(
            status_code=400,
            detail="Package must be approved before rendering",
        )
    book = db.get(Book, package.book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    try:
        result = renderer.render_package(package, book)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"package_id": package_id, **result}


@router.post("/packages/{package_id}/approve")
def approve_package(package_id: int, db: Session = Depends(get_db)) -> dict:
    """Approve one revision — un-approves any prior approved revision for the
    same book so there's always a single canonical approved package."""
    package = db.get(ContentPackage, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found")

    (
        db.query(ContentPackage)
        .filter(
            ContentPackage.book_id == package.book_id,
            ContentPackage.id != package_id,
        )
        .update({"is_approved": False}, synchronize_session=False)
    )
    package.is_approved = True

    book = db.get(Book, package.book_id)
    if book is not None:
        book.status = "scheduled"

    db.commit()
    return {"ok": True, "package_id": package_id}


# ---------------------------------------------------------------------------


def _affiliate_links(isbn: str | None) -> tuple[str | None, str | None]:
    """Best-effort affiliate link construction. Missing keys or a failed ASIN
    lookup just leave the corresponding field null."""
    if not isbn:
        return None, None

    amazon_url = None
    if settings.amazon_associate_tag:
        try:
            asin = amazon.lookup_asin(isbn)
            if asin:
                amazon_url = amazon.build_affiliate_url(asin)
        except Exception:
            pass

    bookshop_url = None
    if settings.bookshop_affiliate_id:
        try:
            bookshop_url = amazon.build_bookshop_url(isbn)
        except Exception:
            pass

    return amazon_url, bookshop_url
