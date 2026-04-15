"""Source adapter unit tests (Firecrawl, Goodreads, Amazon Movers, Reddit)."""
from unittest.mock import MagicMock, patch


# --- Firecrawl client ------------------------------------------------------


def test_firecrawl_fetch_markdown_calls_scrape_endpoint():
    from app.config import settings
    from app.services import firecrawl

    settings.firecrawl_api_key = "fc-test"

    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {
        "success": True,
        "data": {"markdown": "# Hello"},
    }
    fake_client.post.return_value = fake_resp
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)

    with patch("httpx.Client", return_value=fake_client):
        md = firecrawl.fetch_markdown("https://example.com")

    assert md == "# Hello"
    fake_client.post.assert_called_once_with(
        "/scrape",
        json={"url": "https://example.com", "formats": ["markdown"]},
    )


def test_firecrawl_missing_key_raises():
    from app.config import settings
    from app.services import firecrawl

    settings.firecrawl_api_key = ""
    try:
        firecrawl.fetch_markdown("https://example.com")
    except RuntimeError as exc:
        assert "FIRECRAWL_API_KEY" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_firecrawl_surfaces_vendor_failure():
    from app.config import settings
    from app.services import firecrawl

    settings.firecrawl_api_key = "fc-test"

    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json.return_value = {"success": False, "error": "rate limited"}
    fake_client.post.return_value = fake_resp
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)

    with patch("httpx.Client", return_value=fake_client):
        try:
            firecrawl.extract_structured(
                "https://example.com", schema={"type": "object"}
            )
        except RuntimeError as exc:
            assert "Firecrawl extract failed" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")


# --- Goodreads -------------------------------------------------------------


def test_goodreads_normalizes_firecrawl_extraction():
    from app.sources import goodreads

    fake_payload = {
        "books": [
            {
                "title": "The Empusium",
                "author": "Olga Tokarczuk",
                "description": "A sanatorium novel.",
                "isbn": "978-0-593-32179-8",
                "cover_url": "https://example/cover.jpg",
                "rank": 1,
            },
            # Empty title should drop
            {"title": "", "author": "nobody"},
            # ISBN that's garbage → stored as None
            {"title": "X", "author": "Y Z", "isbn": "not an isbn"},
        ]
    }
    with patch(
        "app.services.firecrawl.extract_structured", return_value=fake_payload
    ) as mock:
        books = goodreads.fetch_trending()

    mock.assert_called_once()
    # URL includes the current year/month
    url_used = mock.call_args.kwargs.get("url") or mock.call_args.args[0]
    assert "goodreads.com/book/popular_by_date/" in url_used

    assert len(books) == 2
    assert books[0] == {
        "title": "The Empusium",
        "author": "Olga Tokarczuk",
        "isbn": "9780593321798",  # hyphens stripped
        "description": "A sanatorium novel.",
        "cover_url": "https://example/cover.jpg",
        "source_rank": 1,
    }
    assert books[1]["isbn"] is None  # garbage ISBN cleaned


# --- Amazon Movers & Shakers ----------------------------------------------


def test_amazon_movers_normalizes_firecrawl_extraction():
    from app.sources import amazon_movers

    fake_payload = {
        "books": [
            {
                "title": "The Bee Sting",
                "author": "Paul Murray",
                "asin": "0374600317",
                "cover_url": "https://example/cover.jpg",
                "rank": 4,
            },
            # No title → dropped
            {"title": "", "author": "nobody"},
            # Weird-length ASIN → isbn/asin land as None, but title still kept
            {"title": "OK", "author": "Z", "asin": "BAD"},
        ]
    }
    with patch(
        "app.services.firecrawl.extract_structured", return_value=fake_payload
    ):
        books = amazon_movers.fetch_movers()

    assert len(books) == 2
    first = books[0]
    assert first["title"] == "The Bee Sting"
    assert first["isbn"] == "0374600317"  # ASIN doubles as ISBN-10 for print
    assert first["asin"] == "0374600317"
    assert first["source_rank"] == 4
    assert books[1]["isbn"] is None


# --- Reddit ---------------------------------------------------------------


def test_reddit_extracts_book_from_post_titles():
    from app.sources import reddit_trends

    def children(post_titles: list[str]) -> list[dict]:
        return [
            {"data": {"title": t, "score": 100 - i, "selftext": ""}}
            for i, t in enumerate(post_titles)
        ]

    fake_fantasy = {
        "data": {
            "children": children(
                [
                    '"Piranesi" by Susanna Clarke — a masterpiece',
                    "What did you all think of Dune?",  # no pattern match
                    "The Blade Itself by Joe Abercrombie: finally finished it",
                ]
            )
        }
    }
    fake_scifi = {
        "data": {
            "children": children(
                [
                    "Project Hail Mary - Andy Weir is the best thing I read all year",
                    "Random discussion thread",
                ]
            )
        }
    }

    class FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    calls = []

    def fake_get(url, params=None):
        calls.append(url)
        if "Fantasy" in url:
            return FakeResp(fake_fantasy)
        return FakeResp(fake_scifi)

    fake_client = MagicMock()
    fake_client.get = MagicMock(side_effect=fake_get)
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)

    with patch("httpx.Client", return_value=fake_client):
        books = reddit_trends.fetch_reddit_trends()

    titles = {b["title"] for b in books}
    assert "Piranesi" in titles
    assert "The Blade Itself" in titles
    assert "Project Hail Mary" in titles
    assert len(books) == 3  # junk posts dropped
    # Correct subreddits were hit
    assert any("r/Fantasy" in u for u in calls)
    assert any("r/scifi" in u for u in calls)


def test_reddit_dedupes_cross_subreddit_mentions():
    """Same book mentioned in both r/Fantasy and r/scifi → one entry."""
    from app.sources import reddit_trends

    dup = {
        "data": {
            "children": [
                {"data": {"title": '"Piranesi" by Susanna Clarke', "score": 10, "selftext": ""}}
            ]
        }
    }

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return dup

    fake_client = MagicMock()
    fake_client.get = MagicMock(return_value=FakeResp())
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)

    with patch("httpx.Client", return_value=fake_client):
        books = reddit_trends.fetch_reddit_trends()

    assert len(books) == 1


# --- BookTok --------------------------------------------------------------


def test_booktok_returns_empty_list():
    """Intentionally stubbed — see module docstring."""
    from app.sources import booktok

    assert booktok.fetch_booktok() == []
