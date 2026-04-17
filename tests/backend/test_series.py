"""Series CRUD + generate endpoint tests."""
from unittest.mock import patch

import pytest


def _seed_books(client, count=3):
    """Insert books directly via the DB to avoid needing the discover pipeline."""
    from app.db import SessionLocal
    from app.models import Book

    db = SessionLocal()
    ids = []
    for i in range(1, count + 1):
        book = Book(
            title=f"Test Book {i}",
            author=f"Author {i}",
            description=f"Description for book {i}.",
            genre="fantasy",
            status="discovered",
        )
        db.add(book)
        db.commit()
        db.refresh(book)
        ids.append(book.id)
    db.close()
    return ids


class TestSeriesCRUD:
    def test_create_series(self, client):
        resp = client.post("/series", json={
            "title": "Top 5 Fantasy Reads",
            "description": "Best fantasy books for GoT fans",
            "format": "list",
            "series_type": "themed_list",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Top 5 Fantasy Reads"
        assert data["slug"] == "top-5-fantasy-reads"
        assert data["format"] == "list"
        assert data["series_type"] == "themed_list"
        assert data["status"] == "active"
        assert data["books"] == []
        assert data["packages"] == []

    def test_create_duplicate_slug_409(self, client):
        client.post("/series", json={
            "title": "Unique Series",
            "format": "list",
            "series_type": "themed_list",
        })
        resp = client.post("/series", json={
            "title": "Unique Series",
            "format": "list",
            "series_type": "themed_list",
        })
        assert resp.status_code == 409

    def test_list_series(self, client):
        client.post("/series", json={
            "title": "Series A",
            "format": "list",
            "series_type": "themed_list",
        })
        client.post("/series", json={
            "title": "Series B",
            "format": "short_hook",
            "series_type": "multipart_book",
        })
        resp = client.get("/series")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Most recent first
        assert data[0]["title"] == "Series B"

    def test_get_series_404(self, client):
        resp = client.get("/series/9999")
        assert resp.status_code == 404

    def test_attach_books(self, client):
        book_ids = _seed_books(client, 3)
        create = client.post("/series", json={
            "title": "Attach Test",
            "format": "list",
            "series_type": "themed_list",
        })
        series_id = create.json()["id"]

        resp = client.post(
            f"/series/{series_id}/books",
            json={"book_ids": book_ids},
        )
        assert resp.status_code == 200
        books = resp.json()["books"]
        assert len(books) == 3
        assert books[0]["position"] == 1
        assert books[2]["position"] == 3

    def test_attach_books_replaces_existing(self, client):
        book_ids = _seed_books(client, 4)
        create = client.post("/series", json={
            "title": "Replace Test",
            "format": "list",
            "series_type": "themed_list",
        })
        series_id = create.json()["id"]

        # First attach
        client.post(
            f"/series/{series_id}/books",
            json={"book_ids": book_ids[:2]},
        )
        # Replace with different set
        resp = client.post(
            f"/series/{series_id}/books",
            json={"book_ids": book_ids[2:]},
        )
        books = resp.json()["books"]
        assert len(books) == 2
        assert books[0]["book_id"] == book_ids[2]

    def test_attach_missing_book_404(self, client):
        create = client.post("/series", json={
            "title": "Missing Book Test",
            "format": "list",
            "series_type": "themed_list",
        })
        series_id = create.json()["id"]
        resp = client.post(
            f"/series/{series_id}/books",
            json={"book_ids": [9999]},
        )
        assert resp.status_code == 404


class TestSeriesGenerate:
    """Tests for POST /series/{id}/generate with mocked LLM."""

    FAKE_LIST_SCRIPT = {
        "script": (
            "## INTRO\nThe best fantasy books you haven't read yet.\n\n"
            "## BOOK 1: Test Book 1\nAn epic tale of magic.\n\n"
            "## BOOK 2: Test Book 2\nA sweeping adventure.\n\n"
            "## CTA\nLinks in bio for every book on this list."
        ),
        "narration": (
            "The best fantasy books you haven't read yet. [PAUSE] "
            "An epic tale of magic. [PAUSE] "
            "A sweeping adventure. [PAUSE] "
            "Links in bio for every book on this list."
        ),
        "book_word_counts": [
            {"title": "intro", "words": 9},
            {"title": "Test Book 1", "words": 6},
            {"title": "Test Book 2", "words": 4},
            {"title": "cta", "words": 8},
        ],
    }

    FAKE_LIST_SCENES = {
        "scenes": [
            {"label": "intro", "prompt": "Fantasy landscape", "focus": "set the mood"},
            {"label": "Test Book 1", "prompt": "Dark castle", "focus": "epic"},
            {"label": "Test Book 2", "prompt": "Sailing ship", "focus": "adventure"},
            {"label": "cta", "prompt": "Bookshelf warm light", "focus": "inviting"},
        ],
    }

    FAKE_META = {
        "titles": {
            "tiktok": "Top 2 Fantasy Books",
            "yt_shorts": "Top 2 Fantasy Books You Need",
            "ig_reels": "Fantasy Must-Reads",
            "threads": "Two fantasy books to add to your list",
        },
        "hashtags": {
            "tiktok": ["#booktok", "#fantasy"],
            "yt_shorts": ["#shorts", "#booktok"],
            "ig_reels": ["#bookstagram", "#fantasy"],
            "threads": ["#books"],
        },
    }

    def test_generate_list_sync(self, client):
        book_ids = _seed_books(client, 2)
        create = client.post("/series", json={
            "title": "Gen Test List",
            "format": "list",
            "series_type": "themed_list",
        })
        series_id = create.json()["id"]
        client.post(
            f"/series/{series_id}/books",
            json={"book_ids": book_ids},
        )

        with patch("app.services.llm.dispatch") as mock_dispatch:
            mock_dispatch.side_effect = [
                self.FAKE_LIST_SCRIPT,
                self.FAKE_LIST_SCENES,
                self.FAKE_META,
            ]
            resp = client.post(f"/series/{series_id}/generate")

        assert resp.status_code == 200
        data = resp.json()
        assert "package_id" in data
        assert mock_dispatch.call_count == 3

        # Verify the package was created with correct series_id and format
        series_detail = client.get(f"/series/{series_id}").json()
        assert len(series_detail["packages"]) == 1
        pkg = series_detail["packages"][0]
        assert pkg["format"] == "list"
        assert pkg["part_number"] == 1

    def test_generate_no_books_400(self, client):
        create = client.post("/series", json={
            "title": "Empty Series",
            "format": "list",
            "series_type": "themed_list",
        })
        series_id = create.json()["id"]
        resp = client.post(f"/series/{series_id}/generate")
        assert resp.status_code == 400
        assert "No books" in resp.json()["detail"]

    def test_generate_404_series(self, client):
        resp = client.post("/series/9999/generate")
        assert resp.status_code == 404
