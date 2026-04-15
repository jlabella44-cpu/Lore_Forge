"""POST /discover/run — NYT ingest, Qwen genre classify, ISBN dedupe."""
from unittest.mock import patch

NYT_HITS = [
    {
        "title": "The Ghost Orchid",
        "author": "David Baldacci",
        "isbn": "9781538765388",
        "description": "A mystery.",
        "cover_url": None,
        "source_rank": 1,
    },
    {
        "title": "Project Hail Mary",
        "author": "Andy Weir",
        "isbn": "9780593135204",
        "description": "A sci-fi tale.",
        "cover_url": None,
        "source_rank": 2,
    },
]


def test_discover_creates_books(client):
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=NYT_HITS),
        patch(
            "app.services.llm.classify_genre",
            side_effect=[("thriller", 0.85), ("scifi", 0.92)],
        ),
    ):
        res = client.post("/discover/run")

    assert res.status_code == 200
    assert res.json() == {"fetched": 2, "created": 2, "skipped": 0}

    books = client.get("/books").json()
    assert len(books) == 2
    by_title = {b["title"]: b for b in books}
    assert by_title["The Ghost Orchid"]["genre"] == "thriller"
    assert by_title["Project Hail Mary"]["genre"] == "scifi"
    assert all(b["status"] == "discovered" for b in books)


def test_discover_dedupes_on_isbn(client):
    classify = [("thriller", 0.85), ("scifi", 0.92)]
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=NYT_HITS),
        patch("app.services.llm.classify_genre", side_effect=classify),
    ):
        client.post("/discover/run")

    # Second run should not create duplicate books.
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=NYT_HITS),
        patch("app.services.llm.classify_genre", side_effect=classify),
    ):
        res = client.post("/discover/run")

    assert res.json() == {"fetched": 2, "created": 0, "skipped": 2}
    assert len(client.get("/books").json()) == 2


def test_discover_tolerates_classify_failure(client):
    """A flaky Qwen call shouldn't abort the whole discovery run."""
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=NYT_HITS[:1]),
        patch(
            "app.services.llm.classify_genre",
            side_effect=RuntimeError("Qwen down"),
        ),
    ):
        res = client.post("/discover/run")

    assert res.status_code == 200
    assert res.json()["created"] == 1
    book = client.get("/books").json()[0]
    assert book["genre"] is None  # classifier failed; user overrides later


def test_discover_requires_nyt_key(client):
    """If NYT_API_KEY is unset, the source raises RuntimeError; router maps to 400."""
    with patch(
        "app.sources.nyt.fetch_bestsellers",
        side_effect=RuntimeError("NYT_API_KEY is not set"),
    ):
        res = client.post("/discover/run")
    assert res.status_code == 400
    assert "NYT_API_KEY" in res.json()["detail"]
