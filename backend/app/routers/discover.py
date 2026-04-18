"""Discovery fan-out.

One endpoint, one cron. Each run iterates `settings.sources_enabled` and
aggregates hits across every source. Dedupe is per-(item, source):

  * An item appearing on NYT + Goodreads + Reddit → 1 ContentItem row
    + 3 ContentItemSource rows.
  * A second NYT run on the same item → no new ContentItem, no new
    ContentItemSource.

After writes, per-item `score` is recomputed from the item's
ContentItemSource rows using the scoring module's recency-decayed
weights.

Genre classification only fires for genuinely new items; re-ingestion
skips the Claude/Qwen call. Genre + dossier live in the
`ContentItem.research` JSON blob (exposed via the @property accessors
on the model).

Every ingested item is attached to the currently-active Profile. If
no profile is active the ingest falls back to the `books` profile so
the pre-B2 flow stays functional.
"""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.clock import utc_now
from app.config import settings
from app.db import get_db
from app.models import ContentItem, ContentItemSource
from app.scoring import SOURCE_WEIGHTS, recency_multiplier_from, score_book
from app.services import llm
from app.services import profiles as profile_service
from app.sources import amazon_movers, booktok, goodreads, nyt, reddit_trends

router = APIRouter()

# Fetcher registry. Keys match what lands in ContentItemSource.source.
# Lambdas bind late so unittest.mock.patch("app.sources.nyt.fetch_bestsellers")
# is picked up at call time.
FETCHERS: dict[str, Callable[[], list[dict]]] = {
    "nyt": lambda: nyt.fetch_bestsellers(),
    "goodreads": lambda: goodreads.fetch_trending(),
    "amazon_movers": lambda: amazon_movers.fetch_movers(),
    "reddit": lambda: reddit_trends.fetch_reddit_trends(),
    "booktok": lambda: booktok.fetch_booktok(),
}


def _active_profile_id(db: Session) -> int:
    active = profile_service.get_active(db)
    if active is not None:
        return active.id
    # Fall back to the `books` profile seeded in 0009 so single-user
    # dev setups work even if someone toggled everything off.
    books = profile_service.get_by_slug(db, "books")
    if books is None:
        raise HTTPException(
            status_code=500,
            detail="No active profile and no 'books' fallback profile seeded",
        )
    return books.id


@router.post("/run")
def run_discovery(db: Session = Depends(get_db)) -> dict:
    enabled = _parse_enabled(settings.sources_enabled)
    if not enabled:
        raise HTTPException(
            status_code=400,
            detail="No sources enabled. Set SOURCES_ENABLED in .env.",
        )

    profile_id = _active_profile_id(db)

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
            result = _ingest_hit(db, source, hit, profile_id)
            if result == "created":
                created += 1
                new_source_rows += 1
            elif result == "new_source":
                new_source_rows += 1
            else:
                skipped += 1
            # Commit per hit so SQLite releases the write lock between
            # iterations. The cost-recorder's separate session needs the
            # lock to INSERT its CostRecord rows during classify_genre on
            # the NEXT hit; without this, SQLite's single-writer constraint
            # deadlocks the recorder against our own outer txn.
            db.commit()

    if new_source_rows:
        # SessionLocal is autoflush=False, so the ContentItemSource rows
        # we just db.add()'d aren't visible to _recompute_scores' own
        # query yet.
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


def _ingest_hit(db: Session, source: str, hit: dict, profile_id: int) -> str:
    """Insert (or skip) one hit. Returns one of: created, new_source, skipped."""
    isbn = hit.get("isbn")
    # Match by ISBN first (cross-source dedupe); fall back to title+author
    # for sources that don't surface IDs (e.g. Reddit). ISBN lives in the
    # research JSON, so the filter is a JSON_EXTRACT call (works on
    # SQLite 3.38+ and Postgres 12+).
    if isbn:
        existing = (
            db.query(ContentItem)
            .filter(func.json_extract(ContentItem.research, "$.isbn") == isbn)
            .first()
        )
    else:
        existing = (
            db.query(ContentItem)
            .filter(
                ContentItem.title == hit["title"],
                ContentItem.subtitle == hit["author"],
            )
            .first()
        )

    if existing is None:
        genre, confidence = _safe_classify(
            title=hit["title"],
            author=hit["author"],
            description=hit.get("description"),
        )
        weight = SOURCE_WEIGHTS.get(source, 0.0)
        item = ContentItem(
            profile_id=profile_id,
            title=hit["title"],
            subtitle=hit["author"],
            description=hit.get("description"),
            cover_url=hit.get("cover_url"),
            status="discovered",
            score=weight,
            research={},
        )
        if isbn:
            item.isbn = isbn
        if hit.get("asin"):
            item.asin = hit["asin"]
        if genre is not None:
            item.genre = genre
        if confidence is not None:
            item.genre_confidence = confidence
        db.add(item)
        db.flush()
        db.add(ContentItemSource(content_item_id=item.id, source=source, score=weight))
        return "created"

    # Item exists — is this a new source appearance?
    existing_source = (
        db.query(ContentItemSource)
        .filter(
            ContentItemSource.content_item_id == existing.id,
            ContentItemSource.source == source,
        )
        .first()
    )
    if existing_source is not None:
        return "skipped"

    db.add(
        ContentItemSource(
            content_item_id=existing.id,
            source=source,
            score=SOURCE_WEIGHTS.get(source, 0.0),
        )
    )
    # If the earlier ingest lacked ISBN/ASIN and this one has it, upgrade.
    if not existing.isbn and isbn:
        existing.isbn = isbn
    if not existing.asin and hit.get("asin"):
        existing.asin = hit["asin"]
    return "new_source"


def _safe_classify(
    *, title: str, author: str, description: str | None
) -> tuple[str | None, float | None]:
    try:
        return llm.classify_genre(title, author, description)
    except Exception:
        return None, None


def _recompute_scores(db: Session) -> None:
    """For every item that has at least one ContentItemSource, sum the
    weighted recency-decayed source hits → ContentItem.score."""
    now = utc_now()
    items = db.query(ContentItem).all()
    for item in items:
        rows = (
            db.query(ContentItemSource)
            .filter(ContentItemSource.content_item_id == item.id)
            .all()
        )
        if not rows:
            continue
        hits = [
            (cs.source, recency_multiplier_from(cs.discovered_at, now))
            for cs in rows
        ]
        item.score = score_book(hits)
