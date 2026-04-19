"""`prune_stale_renders` + the POST /packages/prune-renders endpoint.

Eligibility: package.rendered_at older than max_age_days AND book.status
is not 'published'. Published videos stay on disk so the creator can
re-publish without re-rendering.
"""
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch


def _make_rendered_package(client, *, rendered_ago_days: int, book_status: str):
    """Seed one book + approved package + simulate an old on-disk render."""
    from app.clock import utc_now
    from app.config import settings
    from app.db import SessionLocal
    from app.models import ContentItem, ContentPackage

    # Seed via /discover/run so we get a real book + source row.
    nyt_hit = [{
        "title": f"X {rendered_ago_days}d {book_status}",
        "author": "Y",
        "isbn": f"978000{rendered_ago_days:03d}{hash(book_status) % 1000:03d}",
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
        book = db.query(ContentItem).order_by(ContentItem.id.desc()).first()
        pkg = ContentPackage(
            content_item_id=book.id,
            revision_number=1,
            narration="test narration",
            is_approved=True,
            rendered_at=utc_now() - timedelta(days=rendered_ago_days),
            rendered_duration_seconds=30.0,
            rendered_size_bytes=12345,
            rendered_narration_hash="deadbeef" * 8,
        )
        db.add(pkg)
        db.flush()
        book.status = book_status
        db.commit()
        package_id = pkg.id
    finally:
        db.close()

    # Drop a fake mp4 so we can confirm the prune deleted it.
    renders_dir = Path(settings.renders_dir).resolve() / str(package_id)
    renders_dir.mkdir(parents=True, exist_ok=True)
    (renders_dir / "out.mp4").write_bytes(b"fake" * 1024)
    return {"package_id": package_id, "work_dir": renders_dir}


def test_prune_removes_old_unpublished_renders(client, monkeypatch):
    old = _make_rendered_package(client, rendered_ago_days=45, book_status="rendered")

    res = client.post("/packages/prune-renders?max_age_days=30")
    assert res.status_code == 200
    body = res.json()
    assert body["removed_count"] == 1
    assert old["package_id"] in body["removed_package_ids"]
    assert not old["work_dir"].exists()

    # Metadata on the package is cleared so the UI stops showing stale stats.
    detail = client.get(f"/items").json()
    # Fetch the package via /books/{id}
    # (we don't know the book id directly, but the test's single row is easy)
    book_id = detail[0]["id"]
    detail = client.get(f"/items/{book_id}").json()
    pkg = detail["packages"][0]
    assert pkg["rendered_at"] is None
    assert pkg["rendered_duration_seconds"] is None
    assert pkg["rendered_size_bytes"] is None
    # needs_rerender flips back to True because there's no hash anymore.
    assert pkg["needs_rerender"] is True


def test_prune_leaves_recent_renders_alone(client):
    recent = _make_rendered_package(client, rendered_ago_days=5, book_status="rendered")

    res = client.post("/packages/prune-renders?max_age_days=30")
    assert res.status_code == 200
    assert res.json()["removed_count"] == 0
    assert recent["work_dir"].exists()


def test_prune_leaves_published_renders_alone(client):
    """Published videos stay on disk even if they're ancient — re-publish
    shouldn't require a fresh render."""
    published = _make_rendered_package(
        client, rendered_ago_days=90, book_status="published"
    )

    res = client.post("/packages/prune-renders?max_age_days=30")
    assert res.status_code == 200
    assert res.json()["removed_count"] == 0
    assert published["work_dir"].exists()


def test_prune_uses_settings_default_when_no_query_param(client):
    """`max_age_days` query param is optional — falls back to
    settings.render_retention_days (30 in the default config)."""
    old = _make_rendered_package(
        client, rendered_ago_days=40, book_status="rendered"
    )
    res = client.post("/packages/prune-renders")
    assert res.status_code == 200
    assert res.json()["removed_count"] == 1
    assert not old["work_dir"].exists()


def test_prune_400s_when_retention_disabled(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "render_retention_days", 0)
    res = client.post("/packages/prune-renders")
    assert res.status_code == 400
    assert "disabled" in res.json()["detail"].lower()


def test_prune_400s_when_settings_negative(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "render_retention_days", -5)
    res = client.post("/packages/prune-renders")
    assert res.status_code == 400


def test_prune_override_can_run_even_if_settings_disabled(client, monkeypatch):
    """Explicit ?max_age_days=N should work even when the setting is 0."""
    from app.config import settings

    old = _make_rendered_package(
        client, rendered_ago_days=10, book_status="rendered"
    )
    monkeypatch.setattr(settings, "render_retention_days", 0)

    res = client.post("/packages/prune-renders?max_age_days=5")
    assert res.status_code == 200
    assert res.json()["removed_count"] == 1
    assert not old["work_dir"].exists()


def test_prune_clears_metadata_even_when_dir_missing(client):
    """If the on-disk dir is already gone (manual rm, renders_dir moved),
    prune should still clear the package's rendered_* snapshot so the UI
    doesn't keep claiming there's a video."""
    from app.config import settings

    pkg = _make_rendered_package(
        client, rendered_ago_days=45, book_status="rendered"
    )
    # Simulate the dir having been hand-deleted before prune ran.
    import shutil
    shutil.rmtree(pkg["work_dir"])

    res = client.post("/packages/prune-renders?max_age_days=30")
    assert res.status_code == 200
    assert res.json()["removed_count"] == 1
    assert res.json()["freed_bytes"] == 0

    # Metadata still cleared.
    books = client.get("/items").json()
    detail = client.get(f"/items/{books[0]['id']}").json()
    assert detail["packages"][0]["rendered_at"] is None
