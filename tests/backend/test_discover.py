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
    body = res.json()
    assert body["fetched"] == 2
    assert body["created"] == 2
    assert body["skipped"] == 0
    assert body["new_source_rows"] == 2
    assert body["per_source"] == {"nyt": {"fetched": 2}}

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

    # Second run should not create duplicate books or duplicate source rows.
    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=NYT_HITS),
        patch("app.services.llm.classify_genre", side_effect=classify),
    ):
        res = client.post("/discover/run")

    body = res.json()
    assert body["created"] == 0
    assert body["skipped"] == 2
    assert body["new_source_rows"] == 0
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


def test_discover_captures_source_error_per_source(client):
    """A RuntimeError from a source lands in per_source[...]["error"]; the
    run returns 200 so other sources can still contribute. When only NYT
    is enabled and it dies, we get a 200 with a clear per-source error."""
    with patch(
        "app.sources.nyt.fetch_bestsellers",
        side_effect=RuntimeError("NYT_API_KEY is not set"),
    ):
        res = client.post("/discover/run")

    assert res.status_code == 200
    body = res.json()
    assert body["fetched"] == 0
    assert body["created"] == 0
    assert "NYT_API_KEY" in body["per_source"]["nyt"]["error"]


def test_discover_no_sources_enabled_is_400(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "sources_enabled", "")
    res = client.post("/discover/run")
    assert res.status_code == 400
    assert "No sources enabled" in res.json()["detail"]


def test_discover_multi_source_adds_source_rows_to_existing_book(client, monkeypatch):
    """A book that shows up in both NYT and Goodreads gets ONE ContentItem row +
    TWO ContentItemSource rows. Aggregate score sums the weighted contributions."""
    from app.config import settings

    monkeypatch.setattr(settings, "sources_enabled", "nyt,goodreads")

    # Same ISBN in both sources → single ContentItem, two sources, combined score.
    nyt_hits = [
        {
            "title": "The Night Circus",
            "author": "Erin Morgenstern",
            "isbn": "9780307744432",
            "description": "Two magicians duel.",
            "cover_url": None,
            "source_rank": 1,
        }
    ]
    goodreads_hits = [
        {
            "title": "The Night Circus",
            "author": "Erin Morgenstern",
            "isbn": "9780307744432",
            "description": None,
            "cover_url": None,
            "source_rank": 3,
        }
    ]

    with (
        patch("app.sources.nyt.fetch_bestsellers", return_value=nyt_hits),
        patch("app.sources.goodreads.fetch_trending", return_value=goodreads_hits),
        patch("app.services.llm.classify_genre", return_value=("fantasy", 0.9)),
    ):
        res = client.post("/discover/run")

    body = res.json()
    assert body["created"] == 1  # only one ContentItem row
    assert body["new_source_rows"] == 2  # two ContentItemSource rows

    # Aggregate score: nyt(2.0) + goodreads(2.0), both fresh → 4.0
    books = client.get("/books").json()
    assert len(books) == 1
    assert books[0]["score"] == 4.0


def test_discover_reddit_only_no_isbn_dedupes_by_title_author(client, monkeypatch):
    """Reddit hits don't carry ISBNs; dedupe must fall back to
    (title, author) so repeated Reddit runs stay idempotent."""
    from app.config import settings

    monkeypatch.setattr(settings, "sources_enabled", "reddit")

    reddit_hits = [
        {
            "title": "Piranesi",
            "author": "Susanna Clarke",
            "isbn": None,
            "description": None,
            "cover_url": None,
            "source_rank": 1,
        }
    ]

    with (
        patch("app.sources.reddit_trends.fetch_reddit_trends", return_value=reddit_hits),
        patch("app.services.llm.classify_genre", return_value=("fantasy", 0.8)),
    ):
        first = client.post("/discover/run").json()
        second = client.post("/discover/run").json()

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["skipped"] == 1
