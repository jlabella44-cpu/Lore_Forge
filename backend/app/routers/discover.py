"""Discovery endpoint — Phase 1 runs NYT only.

Each run hits the NYT Bestsellers API, classifies each new book's genre via
Qwen, and persists rows to `books` + `book_sources`. Existing books (matched
by ISBN) are skipped; re-ingest logic lands in Phase 2 with dedupe + scoring.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Book, BookSource
from app.scoring import SOURCE_WEIGHTS
from app.services import llm
from app.sources import nyt

router = APIRouter()


@router.post("/run")
def run_discovery(db: Session = Depends(get_db)) -> dict:
    try:
        hits = nyt.fetch_bestsellers()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    nyt_weight = SOURCE_WEIGHTS["nyt"]
    created = 0
    skipped = 0

    for hit in hits:
        isbn = hit.get("isbn")
        # ISBN is our natural key for dedupe. If it's missing (rare on NYT),
        # fall back to (title, author) — good enough for Phase 1.
        q = db.query(Book)
        existing = (
            q.filter(Book.isbn == isbn).first()
            if isbn
            else q.filter(Book.title == hit["title"], Book.author == hit["author"]).first()
        )
        if existing:
            skipped += 1
            continue

        genre, confidence = _safe_classify(
            title=hit["title"],
            author=hit["author"],
            description=hit.get("description"),
        )

        book = Book(
            title=hit["title"],
            author=hit["author"],
            isbn=isbn,
            description=hit.get("description"),
            cover_url=hit.get("cover_url"),
            genre=genre,
            genre_confidence=confidence,
            status="discovered",
            score=nyt_weight,
        )
        db.add(book)
        db.flush()  # materialize book.id
        db.add(BookSource(book_id=book.id, source="nyt", score=nyt_weight))
        created += 1

    db.commit()
    return {"fetched": len(hits), "created": created, "skipped": skipped}


def _safe_classify(
    *, title: str, author: str, description: str | None
) -> tuple[str | None, float | None]:
    """Classification is best-effort — a single bad response shouldn't tank
    the whole discovery run. Book lands with genre=None, user overrides."""
    try:
        return llm.classify_genre(title, author, description)
    except Exception:
        return None, None
