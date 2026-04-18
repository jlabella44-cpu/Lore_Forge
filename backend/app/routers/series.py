"""Series CRUD + generate endpoint.

A Series groups ContentPackages by theme, format, and narrative arc.
The generate endpoint dispatches to the format-specific pipeline
(e.g. LIST → multi-book list video).
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ContentItem, ContentPackage
from app.models.series import Series, SeriesBook
from app.services import cost, jobs
from app.routers.generate import _generate_core_with_progress

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CreateSeriesRequest(BaseModel):
    title: str
    description: str | None = None
    format: str  # VideoFormat value
    series_type: str
    source_book_id: int | None = None
    source_author: str | None = None
    total_parts: int | None = None


class AttachBooksRequest(BaseModel):
    book_ids: list[int]


class GenerateSeriesRequest(BaseModel):
    note: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:128]


def _series_to_dict(s: Series, db: Session) -> dict:
    books = (
        db.query(SeriesBook)
        .filter(SeriesBook.series_id == s.id)
        .order_by(SeriesBook.position)
        .all()
    )
    packages = (
        db.query(ContentPackage)
        .filter(ContentPackage.series_id == s.id)
        .order_by(ContentPackage.part_number)
        .all()
    )
    return {
        "id": s.id,
        "slug": s.slug,
        "title": s.title,
        "description": s.description,
        "format": s.format,
        "series_type": s.series_type,
        "source_book_id": s.source_content_item_id,
        "source_author": s.source_author,
        "total_parts": s.total_parts,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "books": [
            {"book_id": sb.content_item_id, "position": sb.position}
            for sb in books
        ],
        "packages": [
            {
                "id": p.id,
                "part_number": p.part_number,
                "format": p.format,
                "is_approved": p.is_approved,
            }
            for p in packages
        ],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("")
def create_series(body: CreateSeriesRequest, db: Session = Depends(get_db)) -> dict:
    slug = _slugify(body.title)
    existing = db.query(Series).filter(Series.slug == slug).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Series slug {slug!r} already exists")

    series = Series(
        slug=slug,
        title=body.title,
        description=body.description,
        format=body.format,
        series_type=body.series_type,
        source_content_item_id=body.source_book_id,
        source_author=body.source_author,
        total_parts=body.total_parts,
    )
    db.add(series)
    db.commit()
    db.refresh(series)
    return _series_to_dict(series, db)


@router.get("")
def list_series(db: Session = Depends(get_db)) -> list[dict]:
    all_series = (
        db.query(Series)
        .order_by(Series.created_at.desc(), Series.id.desc())
        .all()
    )
    return [_series_to_dict(s, db) for s in all_series]


@router.get("/{series_id}")
def get_series(series_id: int, db: Session = Depends(get_db)) -> dict:
    series = db.get(Series, series_id)
    if series is None:
        raise HTTPException(status_code=404, detail="Series not found")
    return _series_to_dict(series, db)


@router.post("/{series_id}/books")
def attach_books(
    series_id: int,
    body: AttachBooksRequest,
    db: Session = Depends(get_db),
) -> dict:
    series = db.get(Series, series_id)
    if series is None:
        raise HTTPException(status_code=404, detail="Series not found")

    # Clear existing attachments and re-attach in order.
    db.query(SeriesBook).filter(SeriesBook.series_id == series_id).delete()
    for i, item_id in enumerate(body.book_ids, 1):
        item = db.get(ContentItem, item_id)
        if item is None:
            raise HTTPException(
                status_code=404, detail=f"Item {item_id} not found"
            )
        db.add(
            SeriesBook(
                series_id=series_id, content_item_id=item_id, position=i
            )
        )
    db.commit()
    return _series_to_dict(series, db)


@router.post("/{series_id}/generate")
def generate_series(
    series_id: int,
    body: GenerateSeriesRequest | None = None,
    response: Response = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    asynchronous: bool = Query(False, alias="async"),
) -> dict:
    """Generate content for a series. For LIST format: produces one
    ContentPackage covering all attached books."""
    series = db.get(Series, series_id)
    if series is None:
        raise HTTPException(status_code=404, detail="Series not found")

    note = (body or GenerateSeriesRequest()).note

    try:
        cost.assert_under_budget()
    except cost.BudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    # Gather attached books in position order.
    series_books = (
        db.query(SeriesBook)
        .filter(SeriesBook.series_id == series_id)
        .order_by(SeriesBook.position)
        .all()
    )
    books = [db.get(ContentItem, sb.content_item_id) for sb in series_books]
    books = [b for b in books if b is not None]

    if not books:
        raise HTTPException(
            status_code=400, detail="No items attached to this series"
        )

    # Use the first book as the anchor (for revision tracking / affiliate).
    anchor = books[0]
    genre = anchor.genre_override or anchor.genre or "other"

    # Determine part_number for this generation.
    existing_parts = (
        db.query(ContentPackage)
        .filter(ContentPackage.series_id == series_id)
        .count()
    )
    part_number = existing_parts + 1

    if asynchronous:
        job_id = jobs.enqueue(
            "generate",
            anchor.id,
            _series_generate_worker,
            series_id=series_id,
            note=note,
        )
        if response is not None:
            response.status_code = 202
        return {"job_id": job_id, "status": "queued"}

    # Synchronous path.
    from app.services import cost as cost_svc

    with cost_svc.collect_pending() as pending_cost_ids:
        result = _generate_core_with_progress(
            db,
            anchor,
            genre,
            note,
            lambda _msg: None,
            fmt=series.format,
            series_id=series_id,
            part_number=part_number,
            books_for_list=books,
        )
    cost_svc.attach_pending_to(result["package_id"], pending_cost_ids)
    return result


def _series_generate_worker(
    job_id: int, *, series_id: int, note: str | None
) -> None:
    with jobs.job_session(job_id) as (db, set_progress):
        series = db.get(Series, series_id)
        if series is None:
            raise RuntimeError(f"Series {series_id} not found")

        series_books = (
            db.query(SeriesBook)
            .filter(SeriesBook.series_id == series_id)
            .order_by(SeriesBook.position)
            .all()
        )
        books = [db.get(ContentItem, sb.content_item_id) for sb in series_books]
        books = [b for b in books if b is not None]
        if not books:
            raise RuntimeError("No items attached to series")

        anchor = books[0]
        genre = anchor.genre_override or anchor.genre or "other"

        existing_parts = (
            db.query(ContentPackage)
            .filter(ContentPackage.series_id == series_id)
            .count()
        )
        part_number = existing_parts + 1

        from app.services import cost as cost_svc

        with cost_svc.collect_pending() as pending_cost_ids:
            result = _generate_core_with_progress(
                db,
                anchor,
                genre,
                note,
                set_progress,
                fmt=series.format,
                series_id=series_id,
                part_number=part_number,
                books_for_list=books,
            )
        cost_svc.attach_pending_to(result["package_id"], pending_cost_ids)
        set_progress.result(result)
