"""Unit tests for backend/app/services/book_research.py::build_dossier."""
from unittest.mock import patch

import pytest


_FAKE_DOSSIER = {
    "setting": {"name": "drowned city", "era": "", "atmosphere": ""},
    "visual_motifs": ["glowing coral lattice", "broken lighthouse"],
}


def _make_book(client, *, description: str, isbn: str | None = None):
    """Create a ContentItem row directly in the test DB and return it attached
    to a fresh session (so build_dossier can call object_session().commit)."""
    from app import db as db_module
    from app.models import ContentItem

    session = db_module.SessionLocal()
    book = ContentItem(
        profile_id=1,
        title="Test Title",
        subtitle="Test Author",
        description=description,
        isbn=isbn,
        genre="thriller",
    )
    session.add(book)
    session.commit()
    session.refresh(book)
    return session, book


def test_build_dossier_returns_cached_when_populated(client):
    """If book.dossier is already set, build_dossier returns it without
    calling the LLM."""
    from app.services import book_research

    session, book = _make_book(client, description="ok")
    book.dossier = {"setting": {"name": "cached city"}, "visual_motifs": []}
    session.commit()

    with patch("app.services.llm.generate_book_dossier") as llm_mock:
        out = book_research.build_dossier(book)

    assert out == book.dossier
    llm_mock.assert_not_called()
    session.close()


def test_build_dossier_calls_llm_and_persists_on_miss(client):
    """On cache miss, build_dossier calls generate_book_dossier and writes
    the result onto book.dossier."""
    from app.services import book_research

    session, book = _make_book(client, description="a long description " * 50)
    assert book.dossier is None

    with patch(
        "app.services.llm.generate_book_dossier",
        return_value=_FAKE_DOSSIER,
    ) as llm_mock:
        out = book_research.build_dossier(book)

    assert out == _FAKE_DOSSIER
    assert llm_mock.call_count == 1

    # Persisted through the session commit inside build_dossier.
    session.refresh(book)
    assert book.dossier == _FAKE_DOSSIER
    session.close()


def test_build_dossier_skips_firecrawl_when_key_missing(client, monkeypatch):
    """Thin-description book + ISBN but no FIRECRAWL_API_KEY: enrichment
    is silently skipped and the LLM still runs on description alone."""
    from app.config import settings
    from app.services import book_research

    monkeypatch.setattr(settings, "firecrawl_api_key", "")

    session, book = _make_book(
        client, description="one line", isbn="9781538765388"
    )

    # If firecrawl.fetch_markdown were called, this patch would flip the flag.
    called = {"fc": False}

    def _fake_fetch(*_a, **_kw):  # pragma: no cover — must not run
        called["fc"] = True
        return ""

    with (
        patch("app.services.firecrawl.fetch_markdown", side_effect=_fake_fetch),
        patch(
            "app.services.llm.generate_book_dossier",
            return_value=_FAKE_DOSSIER,
        ) as llm_mock,
    ):
        out = book_research.build_dossier(book)

    assert out == _FAKE_DOSSIER
    assert called["fc"] is False
    # LLM was still invoked with scraped_extras=None.
    assert llm_mock.call_args.kwargs["scraped_extras"] is None
    session.close()


def test_build_dossier_swallows_firecrawl_errors(client, monkeypatch):
    """A failing Firecrawl scrape must not abort the build — the LLM
    stage still runs with scraped_extras=None."""
    from app.config import settings
    from app.services import book_research

    monkeypatch.setattr(settings, "firecrawl_api_key", "fake-key")

    session, book = _make_book(
        client, description="one line", isbn="9781538765388"
    )

    with (
        patch(
            "app.services.firecrawl.fetch_markdown",
            side_effect=RuntimeError("firecrawl down"),
        ),
        patch(
            "app.services.llm.generate_book_dossier",
            return_value=_FAKE_DOSSIER,
        ) as llm_mock,
    ):
        out = book_research.build_dossier(book)

    assert out == _FAKE_DOSSIER
    assert llm_mock.call_args.kwargs["scraped_extras"] is None
    session.close()
