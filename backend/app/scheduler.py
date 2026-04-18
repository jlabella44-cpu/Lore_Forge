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
    from sqlalchemy import func

    from app.db import SessionLocal
    from app.sources import nyt
    from app.scoring import SOURCE_WEIGHTS
    from app.models import ContentItem, ContentItemSource
    from app.services import llm
    from app.services import profiles as profile_service

    db = SessionLocal()
    try:
        active = profile_service.get_active(db) or profile_service.get_by_slug(
            db, "books"
        )
        if active is None:
            logger.warning(
                "Weekly discovery cron skipped: no active profile and no "
                "'books' fallback seeded"
            )
            return
        profile_id = active.id

        hits = nyt.fetch_bestsellers()
        weight = SOURCE_WEIGHTS["nyt"]
        for hit in hits:
            isbn = hit.get("isbn")
            # ISBN lives in the research JSON blob after 0010; match
            # via json_extract.
            if isbn:
                existing = (
                    db.query(ContentItem)
                    .filter(
                        func.json_extract(ContentItem.research, "$.isbn")
                        == isbn
                    )
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
            if existing:
                continue
            try:
                genre, confidence = llm.classify_genre(
                    hit["title"], hit["author"], hit.get("description")
                )
            except Exception:
                genre, confidence = None, None
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
            if genre is not None:
                item.genre = genre
            if confidence is not None:
                item.genre_confidence = confidence
            db.add(item)
            db.flush()
            db.add(
                ContentItemSource(
                    content_item_id=item.id, source="nyt", score=weight
                )
            )
        db.commit()
        logger.info("Weekly discovery cron completed — %d hits processed", len(hits))
    except Exception:
        logger.exception("Weekly discovery cron failed")
        db.rollback()
    finally:
        db.close()
