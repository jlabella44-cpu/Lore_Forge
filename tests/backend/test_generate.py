"""POST /books/{id}/generate, POST /packages/{id}/approve."""
from unittest.mock import patch

import pytest

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

SCRIPT_PKG = {
    "script": "HOOK. WORLD TEASE. EMOTIONAL PULL. SOCIAL PROOF. CTA.",
    "visual_prompts": ["p1", "p2", "p3", "p4"],
    "narration": "Words [PAUSE] more words.",
}

META_PKG = {
    "titles": {
        "tiktok": "t",
        "yt_shorts": "y",
        "ig_reels": "i",
        "threads": "th",
    },
    "hashtags": {
        "tiktok": ["#booktok"],
        "yt_shorts": ["#shorts", "#booktok"],
        "ig_reels": ["#bookstagram"],
        "threads": ["#books"],
    },
}


@pytest.fixture
def book_id(client):
    """Seed one book and return its id."""
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=NYT_ONE),
        patch("app.services.llm.classify_genre", return_value=("thriller", 0.85)),
    ):
        client.post("/discover/run")
    return client.get("/books").json()[0]["id"]


@pytest.fixture
def affiliate_env():
    """Set affiliate keys on the live Settings singleton for the test."""
    from app.config import settings

    settings.amazon_associate_tag = "loreforge-20"
    settings.bookshop_affiliate_id = "loreforge"
    yield
    settings.amazon_associate_tag = ""
    settings.bookshop_affiliate_id = ""


def test_generate_creates_revision_1(client, book_id, affiliate_env):
    with (
        patch("app.services.llm.generate_script_package", return_value=SCRIPT_PKG),
        patch("app.services.llm.generate_platform_meta", return_value=META_PKG),
    ):
        res = client.post(f"/books/{book_id}/generate", json={})

    assert res.status_code == 200
    assert res.json()["revision_number"] == 1

    detail = client.get(f"/books/{book_id}").json()
    assert detail["status"] == "review"
    assert len(detail["packages"]) == 1
    pkg = detail["packages"][0]
    assert pkg["script"].startswith("HOOK")
    assert len(pkg["visual_prompts"]) == 4
    assert pkg["titles"]["tiktok"] == "t"
    assert pkg["hashtags"]["yt_shorts"] == ["#shorts", "#booktok"]
    # ISBN-13 9781538765388 → ISBN-10 1538765381 (our amazon.isbn13_to_isbn10)
    assert pkg["affiliate_amazon"] == "https://www.amazon.com/dp/1538765381/?tag=loreforge-20"
    assert (
        pkg["affiliate_bookshop"]
        == "https://bookshop.org/a/loreforge/9781538765388"
    )
    assert pkg["is_approved"] is False


def test_generate_threads_note_into_llm_call(client, book_id):
    with (
        patch(
            "app.services.llm.generate_script_package", return_value=SCRIPT_PKG
        ) as gsp,
        patch("app.services.llm.generate_platform_meta", return_value=META_PKG),
    ):
        client.post(f"/books/{book_id}/generate", json={"note": "darker hook"})

    assert gsp.call_args.kwargs["note"] == "darker hook"


def test_regenerate_increments_revision(client, book_id):
    with (
        patch("app.services.llm.generate_script_package", return_value=SCRIPT_PKG),
        patch("app.services.llm.generate_platform_meta", return_value=META_PKG),
    ):
        client.post(f"/books/{book_id}/generate", json={})
        res = client.post(f"/books/{book_id}/generate", json={"note": "darker"})

    assert res.json()["revision_number"] == 2
    pkgs = client.get(f"/books/{book_id}").json()["packages"]
    assert [p["revision_number"] for p in pkgs] == [2, 1]  # desc order
    assert pkgs[0]["regenerate_note"] == "darker"
    assert pkgs[1]["regenerate_note"] is None


def test_generate_omits_affiliate_when_keys_missing(client, book_id):
    """With no affiliate env vars set, URLs come back null without error."""
    from app.config import settings

    assert settings.amazon_associate_tag == ""  # sanity

    with (
        patch("app.services.llm.generate_script_package", return_value=SCRIPT_PKG),
        patch("app.services.llm.generate_platform_meta", return_value=META_PKG),
    ):
        client.post(f"/books/{book_id}/generate", json={})

    pkg = client.get(f"/books/{book_id}").json()["packages"][0]
    assert pkg["affiliate_amazon"] is None
    assert pkg["affiliate_bookshop"] is None


def test_generate_rollback_on_llm_failure(client, book_id):
    with patch(
        "app.services.llm.generate_script_package",
        side_effect=RuntimeError("Claude exploded"),
    ):
        res = client.post(f"/books/{book_id}/generate", json={})
    assert res.status_code == 502

    # Book status should be restored from "generating" back to the prior state.
    detail = client.get(f"/books/{book_id}").json()
    assert detail["status"] == "discovered"
    assert detail["packages"] == []


def test_approve_is_exclusive(client, book_id):
    """Approving one revision un-approves any other revision on the same book
    and flips the book status to 'scheduled'."""
    with (
        patch("app.services.llm.generate_script_package", return_value=SCRIPT_PKG),
        patch("app.services.llm.generate_platform_meta", return_value=META_PKG),
    ):
        r1 = client.post(f"/books/{book_id}/generate", json={}).json()
        r2 = client.post(f"/books/{book_id}/generate", json={"note": "v2"}).json()

    # Approve revision 2
    assert client.post(f"/packages/{r2['package_id']}/approve").status_code == 200
    detail = client.get(f"/books/{book_id}").json()
    assert detail["status"] == "scheduled"
    by_rev = {p["revision_number"]: p for p in detail["packages"]}
    assert by_rev[2]["is_approved"] is True
    assert by_rev[1]["is_approved"] is False

    # Re-approve revision 1 — revision 2 should flip back to un-approved
    client.post(f"/packages/{r1['package_id']}/approve")
    by_rev = {
        p["revision_number"]: p
        for p in client.get(f"/books/{book_id}").json()["packages"]
    }
    assert by_rev[1]["is_approved"] is True
    assert by_rev[2]["is_approved"] is False


def test_generate_and_approve_404s(client):
    assert client.post("/books/99999/generate").status_code == 404
    assert client.post("/packages/99999/approve").status_code == 404
