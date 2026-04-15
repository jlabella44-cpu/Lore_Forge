"""Discovery fan-out.

One endpoint, one cron. Each run iterates `settings.sources_enabled` and
aggregates hits across every source. Dedupe is per-(book, source):

  * A book appearing on NYT + Goodreads + Reddit → 1 Book row + 3
    BookSource rows.
  * A second NYT run on the same book → no new Book, no new BookSource.

After writes, per-book `score` is recomputed from the book's BookSource
rows using the scoring module's recency-decayed weights.

Genre classification only fires for genuinely new books; re-ingestion skips
the Claude/Qwen call.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Book, BookSource
from app.scoring import SOURCE_WEIGHTS, recency_multiplier_from, score_book
from app.services import llm
from app.sources import amazon_movers, booktok, goodreads, nyt, reddit_trends

router = APIRouter()

# Fetcher registry. Keys match what lands in BookSource.source.
# Lambdas bind late so unittest.mock.patch("app.sources.nyt.fetch_bestsellers")
# is picked up at call time.
FETCHERS: dict[str, Callable[[], list[dict]]] = {
    "nyt": lambda: nyt.fetch_bestsellers(),
    "goodreads": lambda: goodreads.fetch_trending(),
    "amazon_movers": lambda: amazon_movers.fetch_movers(),
    "reddit": lambda: reddit_trends.fetch_reddit_trends(),
    "booktok": lambda: booktok.fetch_booktok(),
}


@router.post("/run")
def run_discovery(db: Session = Depends(get_db)) -> dict:
    enabled = _parse_enabled(settings.sources_enabled)
    if not enabled:
        raise HTTPException(
            status_code=400,
            detail="No sources enabled. Set SOURCES_ENABLED in .env.",
        )

    per_source: dict[str, dict] = {}
    total_fetched = 0
    created = 0
    new_source_rows = 0
    skipped = 0

    for source in enabled:
        fetcher = FETCHERS.get(source)
        if fetcher is None:
            per_source[source] = {"error": f"unknown source {source!r}"}
            continue

        try:
            hits = fetcher()
        except RuntimeError as exc:
            # Missing API key / vendor down — don't fail the whole run.
            per_source[source] = {"error": str(exc)}
            continue

        per_source[source] = {"fetched": len(hits)}
        total_fetched += len(hits)

        for hit in hits:
            result = _ingest_hit(db, source, hit)
            if result == "created":
                created += 1
                new_source_rows += 1
            elif result == "new_source":
                new_source_rows += 1
            else:
                skipped += 1

    if new_source_rows:
        # SessionLocal is autoflush=False, so the BookSource rows we just
        # db.add()'d aren't visible to _recompute_scores' own query yet.
        db.flush()
        _recompute_scores(db)

    db.commit()
    return {
        "fetched": total_fetched,
        "created": created,
        "skipped": skipped,
        "new_source_rows": new_source_rows,
        "per_source": per_source,
    }


# ---------------------------------------------------------------------------


def _parse_enabled(raw: str) -> list[str]:
    return [s.strip() for s in (raw or "").split(",") if s.strip()]


def _ingest_hit(db: Session, source: str, hit: dict) -> str:
    """Insert (or skip) one hit. Returns one of: created, new_source, skipped."""
    isbn = hit.get("isbn")
    # Match by ISBN first (cross-source dedupe); fall back to title+author
    # for sources that don't surface IDs (e.g. Reddit).
    q = db.query(Book)
    existing = (
        q.filter(Book.isbn == isbn).first()
        if isbn
        else q.filter(Book.title == hit["title"], Book.author == hit["author"]).first()
    )

    if existing is None:
        genre, confidence = _safe_classify(
            title=hit["title"],
            author=hit["author"],
            description=hit.get("description"),
        )
        weight = SOURCE_WEIGHTS.get(source, 0.0)
        book = Book(
            title=hit["title"],
            author=hit["author"],
            isbn=isbn,
            asin=hit.get("asin"),
            description=hit.get("description"),
            cover_url=hit.get("cover_url"),
            genre=genre,
            genre_confidence=confidence,
            status="discovered",
            score=weight,
        )
        db.add(book)
        db.flush()
        db.add(BookSource(book_id=book.id, source=source, score=weight))
        return "created"

    # Book exists — is this a new source appearance?
    existing_source = (
        db.query(BookSource)
        .filter(BookSource.book_id == existing.id, BookSource.source == source)
        .first()
    )
    if existing_source is not None:
        return "skipped"

    db.add(
        BookSource(
            book_id=existing.id,
            source=source,
            score=SOURCE_WEIGHTS.get(source, 0.0),
        )
    )
    # If the earlier ingest failed to get ISBN/ASIN and this one has it, upgrade.
    if not existing.isbn and isbn:
        existing.isbn = isbn
    if not existing.asin and hit.get("asin"):
        existing.asin = hit.get("asin")
    return "new_source"


def _safe_classify(
    *, title: str, author: str, description: str | None
) -> tuple[str | None, float | None]:
    try:
        return llm.classify_genre(title, author, description)
    except Exception:
        return None, None


def _recompute_scores(db: Session) -> None:
    """For every book that has at least one BookSource, sum the weighted
    recency-decayed source hits → Book.score."""
    now = datetime.utcnow()
    books = db.query(Book).all()
    for book in books:
        rows = (
            db.query(BookSource)
            .filter(BookSource.book_id == book.id)
            .all()
        )
        if not rows:
            continue
        hits = [
            (bs.source, recency_multiplier_from(bs.discovered_at, now))
            for bs in rows
        ]
        book.score = score_book(hits)
