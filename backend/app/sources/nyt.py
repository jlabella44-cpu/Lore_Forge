"""NYT Bestsellers source — Phase 1 ticket #2.

Hits `https://api.nytimes.com/svc/books/v3/lists/current/combined-print-and-e-book-fiction.json`
Returns a list of dicts: [{title, author, isbn, description, cover_url}, ...]
"""
from __future__ import annotations


def fetch_bestsellers() -> list[dict]:
    raise NotImplementedError
