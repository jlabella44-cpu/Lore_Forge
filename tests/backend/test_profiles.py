"""Profile model + service + 0009 migration seed."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.profile import Profile
from app.services import profiles as profile_service


# ---------------------------------------------------------------------------
# Service — directly populates the table via the model (no migration needed).
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session(tmp_path):
    url = f"sqlite:///{tmp_path / 'p.sqlite'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _mk(db, slug: str, *, active: bool = False) -> Profile:
    p = Profile(
        slug=slug,
        name=slug.title(),
        entity_label=slug.capitalize(),
        active=active,
        sources_config=[],
        prompts={},
        taxonomy=[],
        cta_fields=[],
        render_tones={},
    )
    db.add(p)
    db.flush()
    return p


def test_get_active_returns_the_flagged_row(db_session):
    _mk(db_session, "books", active=True)
    _mk(db_session, "movies", active=False)
    got = profile_service.get_active(db_session)
    assert got is not None and got.slug == "books"


def test_get_active_returns_none_when_nothing_active(db_session):
    _mk(db_session, "books", active=False)
    assert profile_service.get_active(db_session) is None


def test_get_by_slug_finds_and_misses(db_session):
    _mk(db_session, "books")
    assert profile_service.get_by_slug(db_session, "books") is not None
    assert profile_service.get_by_slug(db_session, "nope") is None


def test_list_all_sorted_by_slug(db_session):
    _mk(db_session, "movies")
    _mk(db_session, "books")
    _mk(db_session, "recipes")
    got = [p.slug for p in profile_service.list_all(db_session)]
    assert got == ["books", "movies", "recipes"]


def test_set_active_toggles_exclusively(db_session):
    _mk(db_session, "books", active=True)
    _mk(db_session, "movies", active=False)
    _mk(db_session, "recipes", active=False)

    profile_service.set_active(db_session, "movies")
    db_session.commit()

    active = [p.slug for p in db_session.query(Profile).filter(Profile.active.is_(True))]
    assert active == ["movies"]


def test_set_active_unknown_raises(db_session):
    _mk(db_session, "books")
    with pytest.raises(LookupError, match="nope"):
        profile_service.set_active(db_session, "nope")


def test_set_active_from_nothing_active(db_session):
    """Edge: no row active yet (fresh DB before 0009 seeds) — activating
    one row works without a previous active target to clear."""
    _mk(db_session, "books", active=False)
    _mk(db_session, "movies", active=False)

    profile_service.set_active(db_session, "books")
    db_session.commit()

    assert profile_service.get_active(db_session).slug == "books"


# ---------------------------------------------------------------------------
# Migration — drive alembic end-to-end, confirm the Books profile is seeded
# with real JSON (not double-encoded strings).
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_migration_0009_seeds_books_profile(tmp_path):
    db_file = tmp_path / "m.sqlite"
    url = f"sqlite:///{db_file}"

    env = os.environ.copy()
    env["DATABASE_URL"] = url
    # Run alembic as a subprocess so it goes through db/env.py end-to-end
    # (matches what the desktop-mode lifespan does via
    # app.migrations.run_migrations_to_head).
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(REPO_ROOT / "db"),
        env=env,
        check=True,
        capture_output=True,
    )

    engine = create_engine(url)
    try:
        Session = sessionmaker(bind=engine)
        with Session() as s:
            rows = s.query(Profile).all()
            assert len(rows) == 1
            books = rows[0]
            assert books.slug == "books"
            assert books.entity_label == "Book"
            assert books.active is True

            # Confirm JSON columns decoded into real Python structures,
            # not the "[{\"plugin_slug\": ...}]" double-quoted-string
            # shape we'd see if json.dumps ran twice.
            assert isinstance(books.sources_config, list)
            assert {x["plugin_slug"] for x in books.sources_config} == {
                "nyt",
                "goodreads",
                "amazon_movers",
                "reddit_trends",
                "booktok",
            }
            assert isinstance(books.taxonomy, list) and "fantasy" in books.taxonomy
            assert isinstance(books.render_tones, dict)
            assert books.render_tones["fantasy"] == "dark"
            assert isinstance(books.cta_fields, list)
            assert {x["key"] for x in books.cta_fields} == {
                "amazon_url",
                "bookshop_url",
            }
    finally:
        engine.dispose()
