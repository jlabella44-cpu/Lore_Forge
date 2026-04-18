"""Seed sample data so the UI demos without hitting real APIs.

Usage:
    cd backend
    python -m app.seed                 # idempotent — skips rows already present
    python -m app.seed --wipe          # blow away existing items + packages first

Creates:
  * A 'books' Profile row (idempotent — matches migration 0009 so
    `Base.metadata.create_all` setups without running alembic still
    get a working active profile).
  * 3 ContentItems with different genres (fantasy, scifi, romance).
  * One ContentItemSource row per item (NYT) so the queue looks real.
  * A fully-fleshed-out, APPROVED ContentPackage on the fantasy item —
    hook portfolio, section-anchored script, scene prompts, narration,
    word-level captions, per-platform meta. The Render Video button
    will still need real API keys to run, but the rest of the review
    UI is fully populated for demo.

Nothing here calls Anthropic, OpenAI, Dashscope, NYT, or Firecrawl.
Safe to run with empty API keys.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from app import db as db_module
from app.clock import utc_now
from app.config import settings
from app.db import Base
from app.models import ContentItem, ContentItemSource, ContentPackage, Profile


SAMPLES: list[dict] = [
    {
        "title": "The Ghost Orchid",
        "author": "David Baldacci",
        "isbn": "9781538765388",
        "description": "A swamp-town mystery that refuses to stay buried.",
        "cover_url": None,
        "genre": "thriller",
        "genre_confidence": 0.88,
        "score": 2.0,
        "source": "nyt",
    },
    {
        "title": "Project Hail Mary",
        "author": "Andy Weir",
        "isbn": "9780593135204",
        "description": "A lone astronaut has to save humanity from extinction.",
        "cover_url": None,
        "genre": "scifi",
        "genre_confidence": 0.96,
        "score": 2.0,
        "source": "nyt",
    },
    {
        "title": "The Invisible Life of Addie LaRue",
        "author": "V. E. Schwab",
        "isbn": "9780765387561",
        "description": "A cursed immortal meets someone who remembers her.",
        "cover_url": None,
        "genre": "fantasy",
        "genre_confidence": 0.93,
        "score": 2.0,
        "source": "nyt",
    },
]


# A hand-authored package for the fantasy book, shaped exactly like the
# staged-chain pipeline produces so every review-panel section renders.
SAMPLE_PACKAGE = {
    "hook_alternatives": [
        {
            "angle": "curiosity",
            "text": "What would you do if everyone you loved forgot you the moment you turned your back?",
        },
        {
            "angle": "fear",
            "text": "One deal with the devil. Three hundred years of being invisible.",
        },
        {
            "angle": "promise",
            "text": "If you loved The Night Circus, Addie LaRue will haunt your reading list for months.",
        },
    ],
    "chosen_hook_index": 1,
    "script": (
        "## HOOK\n"
        "One deal with the devil. Three hundred years of being invisible.\n\n"
        "## WORLD TEASE\n"
        "1714. A French village. A young woman trades her soul for freedom — "
        "and pays for it with something far crueler than death.\n\n"
        "## EMOTIONAL PULL\n"
        "Every person Addie meets forgets her the moment she leaves the room. "
        "Until, one day in New York, a bookstore clerk says the impossible: "
        "\"I remember you.\"\n\n"
        "## SOCIAL PROOF\n"
        "2.4 million copies sold. #1 New York Times bestseller. Goodreads 4.19.\n\n"
        "## CTA\n"
        "Link in bio to grab it."
    ),
    "narration": (
        "One deal with the devil. [PAUSE] Three hundred years of being invisible. "
        "Seventeen-fourteen. A French village. A young woman trades her soul for "
        "freedom, and pays for it with something far crueler than death. Every "
        "person Addie meets forgets her the moment she leaves the room. [PAUSE] "
        "Until, one day in New York, a bookstore clerk says the impossible: I "
        "remember you. Two-point-four million copies sold. Number one New York "
        "Times bestseller. Link in bio to grab it."
    ),
    "section_word_counts": {
        "hook": 10,
        "world_tease": 26,
        "emotional_pull": 33,
        "social_proof": 12,
        "cta": 6,
    },
    "visual_prompts": [
        {
            "section": "hook",
            "prompt": "A single candle burning in an ornate mirror at midnight, "
                      "reflected flame warping into a horned silhouette, moody "
                      "oil-painting aesthetic, 9:16",
            "focus": "devil's bargain tease",
        },
        {
            "section": "world_tease",
            "prompt": "A stone French village at dusk in early 1700s, wet "
                      "cobblestones, warm windows, a solitary figure walking "
                      "away down the lane, cinematic fog, 9:16",
            "focus": "setting the 1714 world",
        },
        {
            "section": "emotional_pull",
            "prompt": "Silhouette of a woman from behind standing at a "
                      "rain-slicked window, neon reflections of New York at "
                      "night, wistful and lonely, 9:16",
            "focus": "the curse of being forgotten",
        },
        {
            "section": "social_proof",
            "prompt": "A stack of hardcover books glowing warmly on a vintage "
                      "wooden table, golden-hour light streaming through a "
                      "library window, 9:16",
            "focus": "bestseller status",
        },
        {
            "section": "cta",
            "prompt": "A leather-bound book open on a velvet chair with soft "
                      "lamplight, vintage bookshop atmosphere, inviting and "
                      "warm, 9:16",
            "focus": "warm CTA",
        },
    ],
    "captions": [
        {"word": "One", "start": 0.10, "end": 0.35},
        {"word": "deal", "start": 0.40, "end": 0.72},
        {"word": "with", "start": 0.78, "end": 0.95},
        {"word": "the", "start": 1.00, "end": 1.12},
        {"word": "devil.", "start": 1.15, "end": 1.68},
        {"word": "Three", "start": 2.10, "end": 2.50},
        {"word": "hundred", "start": 2.55, "end": 3.05},
        {"word": "years", "start": 3.10, "end": 3.45},
        {"word": "of", "start": 3.48, "end": 3.62},
        {"word": "being", "start": 3.65, "end": 3.95},
        {"word": "invisible.", "start": 4.00, "end": 4.82},
    ],
    "titles": {
        "tiktok": "She traded her soul for freedom. The price was being forgotten.",
        "yt_shorts": "300 years invisible. One bookstore clerk. The Addie LaRue effect",
        "ig_reels": "If you loved Night Circus you need this book on your TBR",
        "threads": "Just finished The Invisible Life of Addie LaRue and I need to talk about it.",
    },
    "hashtags": {
        "tiktok": ["#booktok", "#fantasybooktok", "#bookrecs", "#veschwab", "#addielarue"],
        "yt_shorts": ["#shorts", "#booktok", "#fantasybooks", "#bookreview", "#veschwab"],
        "ig_reels": ["#bookstagram", "#fantasyreads", "#booklover", "#addielarue"],
        "threads": ["#books", "#bookrecs", "#fantasy", "#addielarue"],
    },
    "affiliate_amazon": None,      # Filled in when a real tag is configured
    "affiliate_bookshop": None,
    "regenerate_note": None,
    "is_approved": True,
}


# Mirrors migration 0009's seeded Books profile. Duplicated so seed.py
# works on setups that used `Base.metadata.create_all` instead of
# `alembic upgrade head` (e.g. pytest fixtures).
_BOOKS_PROFILE = dict(
    slug="books",
    name="Books",
    entity_label="Book",
    description="Seeded by app.seed — Books profile.",
    active=True,
    sources_config=[
        {"plugin_slug": "nyt", "config": {}},
        {"plugin_slug": "goodreads", "config": {}},
        {"plugin_slug": "amazon_movers", "config": {}},
        {"plugin_slug": "reddit_trends", "config": {}},
        {"plugin_slug": "booktok", "config": {}},
    ],
    prompts={
        "hook_system": "",
        "script_system": "",
        "scene_prompts_system": "",
        "meta_system": "",
    },
    taxonomy=["fantasy", "thriller", "scifi", "romance", "historical_fiction", "other"],
    cta_fields=[
        {"key": "amazon_url", "label": "Amazon"},
        {"key": "bookshop_url", "label": "Bookshop"},
    ],
    render_tones={
        "fantasy": "dark",
        "thriller": "dark",
        "scifi": "hype",
        "romance": "cozy",
        "historical_fiction": "cozy",
        "other": "dark",
    },
)


def _ensure_books_profile(db) -> Profile:
    profile = db.query(Profile).filter(Profile.slug == "books").first()
    if profile is None:
        profile = Profile(**_BOOKS_PROFILE)
        db.add(profile)
        db.flush()
    return profile


def run(wipe: bool = False, with_video: bool = True) -> dict:
    # Resolve the engine + session lazily so tests that swap db_module.engine
    # via fixtures see the right database. (A module-level `from app.db import
    # SessionLocal` binding would freeze to whatever was current at first
    # import — broken across sequential test files.)
    Base.metadata.create_all(db_module.engine)

    db = db_module.SessionLocal()
    created_items = 0
    created_sources = 0
    created_packages = 0
    rendered_video = False
    try:
        if wipe:
            # Cost records reference packages; clear them first to avoid FK churn.
            from app.models import CostRecord

            db.query(CostRecord).delete()
            db.query(ContentPackage).delete()
            db.query(ContentItemSource).delete()
            db.query(ContentItem).delete()
            db.commit()

        profile = _ensure_books_profile(db)

        for sample in SAMPLES:
            item = (
                db.query(ContentItem)
                .filter(ContentItem.profile_id == profile.id)
                .filter(ContentItem.title == sample["title"])
                .first()
            )
            if item is None:
                item = ContentItem(
                    profile_id=profile.id,
                    title=sample["title"],
                    subtitle=sample["author"],
                    description=sample["description"],
                    cover_url=sample["cover_url"],
                    score=sample["score"],
                    status="discovered",
                    research={},
                )
                # Book-era fields land in research via @property setters.
                item.isbn = sample["isbn"]
                item.genre = sample["genre"]
                item.genre_confidence = sample["genre_confidence"]
                db.add(item)
                db.flush()
                created_items += 1

            existing_source = (
                db.query(ContentItemSource)
                .filter(
                    ContentItemSource.content_item_id == item.id,
                    ContentItemSource.source == sample["source"],
                )
                .first()
            )
            if existing_source is None:
                db.add(
                    ContentItemSource(
                        content_item_id=item.id,
                        source=sample["source"],
                        score=sample["score"],
                    )
                )
                created_sources += 1

            # Fantasy book gets the fleshed-out package.
            if sample["genre"] == "fantasy":
                has_package = (
                    db.query(ContentPackage)
                    .filter(ContentPackage.content_item_id == item.id)
                    .count()
                )
                if has_package == 0:
                    pkg = ContentPackage(
                        content_item_id=item.id,
                        revision_number=1,
                        created_at=utc_now(),
                        **SAMPLE_PACKAGE,
                    )
                    db.add(pkg)
                    db.flush()
                    item.status = "scheduled"
                    if with_video:
                        rendered_video = _render_sample_video(pkg.id)
                        if rendered_video:
                            out_mp4 = (
                                Path(settings.renders_dir).resolve()
                                / str(pkg.id)
                                / "out.mp4"
                            )
                            pkg.rendered_at = utc_now()
                            pkg.rendered_duration_seconds = 5.0
                            pkg.rendered_size_bytes = out_mp4.stat().st_size
                            pkg.rendered_narration_hash = _narration_hash(pkg.narration)
                            item.status = "rendered"
                    created_packages += 1

        db.commit()
    finally:
        db.close()

    return {
        "books_created": created_items,
        "book_sources_created": created_sources,
        "packages_created": created_packages,
        "sample_video_rendered": rendered_video,
    }


def _narration_hash(text: str) -> str:
    # Local import avoids dragging sqlalchemy import order around.
    from app.services.renderer import narration_hash

    return narration_hash(text)


def _render_sample_video(package_id: int) -> bool:
    """Generate a tiny placeholder mp4 at the path /renders/{id}/out.mp4 so
    the item review page's video preview has something to play offline.

    Uses ffmpeg. Returns True on success, False with a printed note if
    ffmpeg isn't installed or the call fails — we never block seeding
    over a demo video.
    """
    if shutil.which("ffmpeg") is None:
        print(
            "  ⚠ ffmpeg not on PATH — skipping sample video. "
            "The review page will still render; the <video> tag just 404s."
        )
        return False

    renders_dir = Path(settings.renders_dir).resolve() / str(package_id)
    renders_dir.mkdir(parents=True, exist_ok=True)
    out = renders_dir / "out.mp4"

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-f", "lavfi",
        "-i", "color=c=0x1a1a24:s=1080x1920:r=30:d=5",
        "-vf",
        (
            "drawtext=text='Sample render':fontcolor=0xc2a657:"
            "fontsize=96:x=(w-text_w)/2:y=(h-text_h)/2-40,"
            "drawtext=text='(seeded, not a real render)':fontcolor=0xc2a657:"
            "fontsize=42:x=(w-text_w)/2:y=(h-text_h)/2+80:alpha=0.7"
        ),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-t", "5",
        str(out),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    except subprocess.SubprocessError as exc:
        print(f"  ⚠ ffmpeg sample render failed: {exc}")
        return False
    print(f"  ✓ sample video at {out}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sample data for the UI.")
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Delete all items + sources + packages before seeding.",
    )
    parser.add_argument(
        "--no-video",
        action="store_true",
        help="Skip ffmpeg sample-video generation (faster; preview will 404).",
    )
    args = parser.parse_args()
    stats = run(wipe=args.wipe, with_video=not args.no_video)
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
