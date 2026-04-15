"""APScheduler bootstrap and Phase 2 job registration.

The scheduler lifecycle is owned by main.py's lifespan: it calls
`register_jobs()` before `scheduler.start()`. Jobs stay opt-in so a
`uvicorn --reload` on a dev machine doesn't rack up API costs.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def register_jobs() -> None:
    """Attach every cron-driven job the app should run. Idempotent — safe to
    call across reloads because it uses fixed job ids with replace_existing.
    """
    if settings.discovery_cron_enabled:
        scheduler.add_job(
            _run_discovery_cron,
            CronTrigger(
                day_of_week=settings.discovery_cron_day,
                hour=settings.discovery_cron_hour,
            ),
            id="weekly_discovery",
            replace_existing=True,
        )
        logger.info(
            "Registered weekly discovery cron: %s @ %02d:00",
            settings.discovery_cron_day,
            settings.discovery_cron_hour,
        )


def _run_discovery_cron() -> None:
    """Scheduled discovery runs in a fresh DB session. Imported lazily so
    registration doesn't pull models into startup if the cron is disabled.
    """
    from app.db import SessionLocal
    from app.sources import nyt
    from app.scoring import SOURCE_WEIGHTS
    from app.models import Book, BookSource
    from app.services import llm

    db = SessionLocal()
    try:
        hits = nyt.fetch_bestsellers()
        weight = SOURCE_WEIGHTS["nyt"]
        for hit in hits:
            isbn = hit.get("isbn")
            existing = (
                db.query(Book).filter(Book.isbn == isbn).first()
                if isbn
                else db.query(Book).filter(
                    Book.title == hit["title"], Book.author == hit["author"]
                ).first()
            )
            if existing:
                continue
            try:
                genre, confidence = llm.classify_genre(
                    hit["title"], hit["author"], hit.get("description")
                )
            except Exception:
                genre, confidence = None, None
            book = Book(
                title=hit["title"],
                author=hit["author"],
                isbn=isbn,
                description=hit.get("description"),
                cover_url=hit.get("cover_url"),
                genre=genre,
                genre_confidence=confidence,
                status="discovered",
                score=weight,
            )
            db.add(book)
            db.flush()
            db.add(BookSource(book_id=book.id, source="nyt", score=weight))
        db.commit()
        logger.info("Weekly discovery cron completed — %d hits processed", len(hits))
    except Exception:
        logger.exception("Weekly discovery cron failed")
        db.rollback()
    finally:
        db.close()
