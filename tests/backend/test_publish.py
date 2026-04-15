"""POST /publish/{package_id}/{platform} — dispatch, guards, persistence."""
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def rendered_package(client, tmp_path, monkeypatch):
    """Seed a fully-approved package with a fake pre-rendered mp4 on disk."""
    from app.config import settings

    monkeypatch.setattr(settings, "renders_dir", str(tmp_path / "renders"))

    nyt_hits = [
        {
            "title": "The Invisible Life of Addie LaRue",
            "author": "V. E. Schwab",
            "isbn": "9780765387561",
            "description": "A cursed immortal meets someone who remembers her.",
            "cover_url": None,
            "source_rank": 1,
        }
    ]
    script_pkg = {
        "script": "HOOK. WORLD TEASE. EMOTIONAL PULL. SOCIAL PROOF. CTA.",
        "visual_prompts": ["p1", "p2", "p3", "p4"],
        "narration": "In a forgotten forest...",
    }
    meta_pkg = {
        "titles": {
            "tiktok": "tt title",
            "yt_shorts": "yt title",
            "ig_reels": "ig title",
            "threads": "th title",
        },
        "hashtags": {
            "tiktok": ["#booktok"],
            "yt_shorts": ["#shorts", "#booktok"],
            "ig_reels": ["#bookstagram"],
            "threads": ["#books"],
        },
    }

    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=nyt_hits),
        patch("app.services.llm.classify_genre", return_value=("fantasy", 0.9)),
    ):
        client.post("/discover/run")

    book_id = client.get("/books").json()[0]["id"]
    with (
        patch("app.services.llm.generate_script_package", return_value=script_pkg),
        patch("app.services.llm.generate_platform_meta", return_value=meta_pkg),
    ):
        gen = client.post(f"/books/{book_id}/generate", json={}).json()

    package_id = gen["package_id"]
    client.post(f"/packages/{package_id}/approve")

    # Stage a fake rendered mp4 at the path the publish router expects
    mp4_dir = Path(settings.renders_dir).resolve() / str(package_id)
    mp4_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = mp4_dir / "out.mp4"
    mp4_path.write_bytes(b"fake_mp4_bytes")
    return {"book_id": book_id, "package_id": package_id, "mp4": mp4_path}


def test_publish_yt_shorts_success(client, rendered_package):
    pid = rendered_package["package_id"]
    with patch("app.services.youtube.upload", return_value="yt_abc123") as m:
        res = client.post(f"/publish/{pid}/yt_shorts")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["platform"] == "yt_shorts"
    assert body["external_id"] == "yt_abc123"
    assert body["video_id"] > 0
    assert "published_at" in body

    # Upload was called with the right title, mp4, and hashtags
    kwargs = m.call_args.kwargs
    assert kwargs["title"] == "yt title"
    assert kwargs["tags"] == ["#shorts", "#booktok"]
    # Description contains the hashtags joined
    assert "#shorts" in kwargs["description"]

    # Book status flipped to published
    bid = rendered_package["book_id"]
    assert client.get(f"/books/{bid}").json()["status"] == "published"


def test_publish_tiktok_success(client, rendered_package):
    pid = rendered_package["package_id"]
    with patch("app.services.tiktok.upload", return_value="tt_xyz789") as m:
        res = client.post(f"/publish/{pid}/tiktok")
    assert res.status_code == 200
    assert res.json()["external_id"] == "tt_xyz789"
    kwargs = m.call_args.kwargs
    assert kwargs["caption"] == "tt title"
    assert kwargs["hashtags"] == ["#booktok"]


def test_publish_missing_credentials_is_502(client, rendered_package):
    """With no YT credentials configured, upload() raises RuntimeError before
    hitting the NotImplementedError stub. Router surfaces that as 502."""
    pid = rendered_package["package_id"]
    res = client.post(f"/publish/{pid}/yt_shorts")
    assert res.status_code == 502
    assert "YOUTUBE_CLIENT" in res.json()["detail"]


def test_publish_not_implemented_surfaces_501(client, rendered_package, monkeypatch):
    """With creds set, the YT stub's NotImplementedError path fires — 501."""
    from app.config import settings

    monkeypatch.setattr(settings, "youtube_client_id", "stub-id")
    monkeypatch.setattr(settings, "youtube_client_secret", "stub-secret")

    pid = rendered_package["package_id"]
    res = client.post(f"/publish/{pid}/yt_shorts")
    assert res.status_code == 501
    assert "not yet wired" in res.json()["detail"]


def test_publish_unknown_platform(client, rendered_package):
    pid = rendered_package["package_id"]
    res = client.post(f"/publish/{pid}/twitter")
    assert res.status_code == 400
    assert "twitter" in res.json()["detail"]


def test_publish_requires_approval(client, rendered_package, monkeypatch):
    """Flip is_approved off in-place to simulate a not-yet-approved package."""
    from app.db import SessionLocal
    from app.models import ContentPackage

    db = SessionLocal()
    try:
        pkg = db.get(ContentPackage, rendered_package["package_id"])
        pkg.is_approved = False
        db.commit()
    finally:
        db.close()

    res = client.post(f"/publish/{rendered_package['package_id']}/yt_shorts")
    assert res.status_code == 400
    assert "approved" in res.json()["detail"].lower()


def test_publish_requires_rendered_mp4(client, rendered_package):
    rendered_package["mp4"].unlink()
    res = client.post(f"/publish/{rendered_package['package_id']}/yt_shorts")
    assert res.status_code == 400
    assert "rendered" in res.json()["detail"].lower()


def test_publish_404_on_missing_package(client):
    assert client.post("/publish/99999/yt_shorts").status_code == 404


def test_publish_ig_reels_requires_public_url(client, rendered_package):
    """Meta platforms need a public URL the renderer doesn't produce yet;
    the router converts the NotImplementedError into a 501."""
    pid = rendered_package["package_id"]
    res = client.post(f"/publish/{pid}/ig_reels")
    assert res.status_code == 501
    assert "public video URL" in res.json()["detail"]


def test_publish_persists_video_row(client, rendered_package):
    pid = rendered_package["package_id"]
    with patch("app.services.youtube.upload", return_value="yt_999"):
        body = client.post(f"/publish/{pid}/yt_shorts").json()

    from app.db import SessionLocal
    from app.models import Video

    db = SessionLocal()
    try:
        video = db.get(Video, body["video_id"])
        assert video is not None
        assert video.platform == "yt_shorts"
        assert video.external_id == "yt_999"
        assert video.package_id == pid
        assert video.file_path.endswith("out.mp4")
        assert video.published_at is not None
    finally:
        db.close()
