"""GET /books, GET /books/{id}, PATCH /books/{id}."""
from unittest.mock import patch

NYT_ONE = [
    {
        "title": "The Ghost Orchid",
        "author": "David Baldacci",
        "isbn": "9781538765388",
        "description": "A mystery.",
        "cover_url": None,
        "source_rank": 1,
    }
]


def _seed_one(client, genre=("thriller", 0.85)):
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=NYT_ONE),
        patch("app.services.llm.classify_genre", return_value=genre),
    ):
        client.post("/discover/run")
    return client.get("/books").json()[0]["id"]


def test_list_books_empty(client):
    res = client.get("/books")
    assert res.status_code == 200
    assert res.json() == []


def test_list_books_returns_effective_genre(client):
    book_id = _seed_one(client)

    # Override — effective genre should flip to fantasy, source should be "override"
    client.patch(f"/books/{book_id}", json={"genre_override": "fantasy"})
    book = client.get("/books").json()[0]
    assert book["genre"] == "fantasy"
    assert book["genre_source"] == "override"

    # Clear override — back to auto-classified thriller
    client.patch(f"/books/{book_id}", json={"genre_override": None})
    book = client.get("/books").json()[0]
    assert book["genre"] == "thriller"
    assert book["genre_source"] == "auto"


def test_get_book_detail(client):
    book_id = _seed_one(client)
    res = client.get(f"/books/{book_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == book_id
    assert detail["title"] == "The Ghost Orchid"
    assert detail["isbn"] == "9781538765388"
    assert detail["packages"] == []


def test_book_404s(client):
    assert client.get("/books/99999").status_code == 404
    assert client.patch("/books/99999", json={}).status_code == 404
    assert client.post("/books/99999/skip").status_code == 404
    assert client.post("/books/99999/unskip").status_code == 404


def test_skip_hides_book_from_default_queue(client):
    book_id = _seed_one(client)
    assert len(client.get("/books").json()) == 1

    assert client.post(f"/books/{book_id}/skip").status_code == 200

    # Default list omits skipped books
    assert client.get("/books").json() == []

    # But include_skipped=true surfaces them
    listed = client.get("/books?include_skipped=true").json()
    assert len(listed) == 1
    assert listed[0]["status"] == "skipped"


def test_unskip_restores_visibility(client):
    book_id = _seed_one(client)
    client.post(f"/books/{book_id}/skip")
    assert client.get("/books").json() == []

    client.post(f"/books/{book_id}/unskip")
    listed = client.get("/books").json()
    assert len(listed) == 1
    assert listed[0]["status"] == "discovered"


def test_patch_can_set_status_directly(client):
    """PATCH /books/{id} with {"status": "published"} is a sharp edge for
    admin/debug; covers the case where someone wants to correct a wedged
    book without hitting the typed skip/unskip endpoints."""
    book_id = _seed_one(client)
    assert client.patch(f"/books/{book_id}", json={"status": "published"}).status_code == 200
    assert client.get(f"/books/{book_id}").json()["status"] == "published"


# ---------- GET /books/history ----------


def _seed_rendered(client, *, rendered_ago_days: int, title: str):
    """Seed one book + one approved package with a simulated render
    N days ago. Returns the package id and rendered_at."""
    from datetime import timedelta

    from app.clock import utc_now
    from app.db import SessionLocal
    from app.models import Book, ContentPackage
    from app.services.renderer import narration_hash

    nyt_hit = [{
        "title": title,
        "author": "Author X",
        "isbn": f"978000{abs(hash(title)) % 10_000_000:07d}",
        "description": None,
        "cover_url": None,
        "source_rank": 1,
    }]
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=nyt_hit),
        patch("app.services.llm.classify_genre", return_value=("fantasy", 0.9)),
    ):
        client.post("/discover/run")

    db = SessionLocal()
    try:
        book = db.query(Book).filter(Book.title == title).one()
        rendered_at = utc_now() - timedelta(days=rendered_ago_days)
        narration = "narration text"
        pkg = ContentPackage(
            book_id=book.id,
            revision_number=1,
            narration=narration,
            is_approved=True,
            rendered_at=rendered_at,
            rendered_duration_seconds=42.5,
            rendered_size_bytes=9_876_543,
            rendered_narration_hash=narration_hash(narration),
        )
        db.add(pkg)
        book.status = "rendered"
        db.commit()
        return {"book_id": book.id, "package_id": pkg.id}
    finally:
        db.close()


def test_history_empty_when_no_renders(client):
    res = client.get("/books/history")
    assert res.status_code == 200
    assert res.json() == []


def test_history_returns_rendered_books_newest_first(client):
    older = _seed_rendered(client, rendered_ago_days=10, title="Older Render")
    newer = _seed_rendered(client, rendered_ago_days=1, title="Newer Render")

    rows = client.get("/books/history").json()
    assert len(rows) == 2
    assert rows[0]["book_id"] == newer["book_id"]
    assert rows[1]["book_id"] == older["book_id"]

    row = rows[0]
    assert row["latest_package_id"] == newer["package_id"]
    assert row["rendered_duration_seconds"] == 42.5
    assert row["rendered_size_bytes"] == 9_876_543
    assert row["status"] == "rendered"
    assert row["needs_rerender"] is False


def test_history_excludes_books_without_renders(client):
    _seed_one(client)  # discovered-only book, no package
    _seed_rendered(client, rendered_ago_days=3, title="Has A Render")

    rows = client.get("/books/history").json()
    assert len(rows) == 1
    assert rows[0]["title"] == "Has A Render"


def test_history_deduplicates_by_book_when_multiple_revisions(client):
    """If a book has two rendered packages, history shows only the most
    recent one — the page is book-centric, not package-centric."""
    from datetime import timedelta

    from app.clock import utc_now
    from app.db import SessionLocal
    from app.models import ContentPackage

    seeded = _seed_rendered(client, rendered_ago_days=5, title="Two Revs")

    # Add a second, more recent rendered revision of the same book.
    db = SessionLocal()
    try:
        recent = ContentPackage(
            book_id=seeded["book_id"],
            revision_number=2,
            narration="v2 narration",
            is_approved=False,
            rendered_at=utc_now() - timedelta(hours=1),
            rendered_duration_seconds=50.0,
            rendered_size_bytes=1_234_567,
            rendered_narration_hash="y" * 64,
        )
        db.add(recent)
        db.commit()
        recent_id = recent.id
    finally:
        db.close()

    rows = client.get("/books/history").json()
    assert len(rows) == 1
    assert rows[0]["latest_package_id"] == recent_id
    assert rows[0]["revision_number"] == 2
    assert rows[0]["rendered_duration_seconds"] == 50.0


def test_history_flags_stale_renders(client):
    """If the narration was edited after the render, needs_rerender=True
    so the UI can warn before the user expects a fresh asset."""
    from app.db import SessionLocal
    from app.models import ContentPackage

    seeded = _seed_rendered(client, rendered_ago_days=2, title="Stale")
    db = SessionLocal()
    try:
        pkg = db.get(ContentPackage, seeded["package_id"])
        pkg.narration = pkg.narration + " (edited after render)"
        db.commit()
    finally:
        db.close()

    rows = client.get("/books/history").json()
    assert rows[0]["needs_rerender"] is True
