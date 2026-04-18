"""Goodreads trending books via Firecrawl structured extraction.

We hit the monthly "Popular Books by Release Date" list, which is the most
stable public Goodreads signal for "what's hot right now" — less noisy than
the homepage trending widget, and not login-gated.

URL shape: https://www.goodreads.com/book/popular_by_date/{YEAR}/{MONTH}
"""
from __future__ import annotations

from datetime import datetime

from app.clock import utc_now
from app.services import firecrawl

_SCHEMA = {
    "type": "object",
    "properties": {
        "books": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "author": {"type": "string"},
                    "description": {"type": "string"},
                    "isbn": {
                        "type": "string",
                        "description": "ISBN-13 or ISBN-10 if visible, else empty",
                    },
                    "cover_url": {"type": "string"},
                    "rank": {"type": "integer"},
                },
                "required": ["title", "author"],
            },
        },
    },
    "required": ["books"],
}

_PROMPT = (
    "Extract every book on the page as a 'books' array. For each book, pull "
    "title, author, description (if shown), ISBN (if visible anywhere on the "
    "card — otherwise empty string), cover_url (book thumbnail URL), and "
    "rank (1-based position on the page). Do not invent fields that aren't "
    "on the page."
)


def fetch_trending(now: datetime | None = None, limit: int = 25) -> list[dict]:
    """Return up to `limit` normalized book rows from the current month's
    Goodreads popularity list."""
    now = now or utc_now()
    url = f"https://www.goodreads.com/book/popular_by_date/{now.year}/{now.month}"

    payload = firecrawl.extract_structured(url, schema=_SCHEMA, prompt=_PROMPT)
    raw_books = payload.get("books", [])[:limit]

    results: list[dict] = []
    for b in raw_books:
        title = (b.get("title") or "").strip()
        author = (b.get("author") or "").strip()
        if not title or not author:
            continue
        results.append(
            {
                "title": title,
                "author": author,
                "isbn": _clean_isbn(b.get("isbn")),
                "description": b.get("description") or None,
                "cover_url": b.get("cover_url") or None,
                "source_rank": b.get("rank"),
            }
        )
    return results


def _clean_isbn(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = "".join(c for c in raw if c.isdigit() or c.upper() == "X")
    if len(digits) in (10, 13):
        return digits
    return None


from app.sources.base import DiscoverySource, register  # noqa: E402


class GoodreadsPlugin(DiscoverySource):
    slug = "goodreads"

    def fetch(self, config=None) -> list[dict]:
        return fetch_trending()


register(GoodreadsPlugin())
