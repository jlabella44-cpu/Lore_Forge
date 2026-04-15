"""NYT Bestsellers source — Phase 1 ticket #2.

Hits the combined-print-and-e-book-fiction list and returns a list of normalized
book dicts the pipeline can ingest. Free tier, requires NYT_API_KEY.

Docs: https://developer.nytimes.com/docs/books-product/1/overview
"""
from __future__ import annotations

import httpx

from app.config import settings

NYT_URL = (
    "https://api.nytimes.com/svc/books/v3/lists/current/"
    "combined-print-and-e-book-fiction.json"
)


def fetch_bestsellers() -> list[dict]:
    """Return normalized book rows:
        {title, author, isbn, description, cover_url, source_rank}
    """
    if not settings.nyt_api_key:
        raise RuntimeError("NYT_API_KEY is not set")

    resp = httpx.get(
        NYT_URL,
        params={"api-key": settings.nyt_api_key},
        timeout=30.0,
    )
    resp.raise_for_status()
    payload = resp.json()
    return [_normalize(b) for b in payload.get("results", {}).get("books", [])]


def _normalize(book: dict) -> dict:
    return {
        "title": _smart_title(book.get("title") or ""),
        "author": _smart_title(book.get("author") or ""),
        "isbn": book.get("primary_isbn13") or book.get("primary_isbn10"),
        "description": book.get("description") or None,
        "cover_url": book.get("book_image") or None,
        "source_rank": book.get("rank"),
    }


def _smart_title(s: str) -> str:
    """NYT returns TITLES IN ALL CAPS. Title-case those; leave mixed-case alone."""
    return s.title() if s and s.isupper() else s
