"""Amazon Movers & Shakers — biggest risers in the last 24h.

High purchase-intent signal. Page is Cloudflare-protected + login-walled for
deep cards, but the landing page has enough per-book data (title, author,
rank change, ASIN in the link) to populate the queue.

URL: https://www.amazon.com/gp/movers-and-shakers/books/
"""
from __future__ import annotations

from app.services import firecrawl

_URL = "https://www.amazon.com/gp/movers-and-shakers/books/"

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
                    "asin": {
                        "type": "string",
                        "description": "10-character ASIN pulled from the /dp/ link",
                    },
                    "cover_url": {"type": "string"},
                    "rank": {"type": "integer"},
                },
                "required": ["title"],
            },
        },
    },
    "required": ["books"],
}

_PROMPT = (
    "Extract the Movers & Shakers book list. For each entry, pull title, "
    "author, asin (10-char alphanumeric product id from the /dp/ URL), "
    "cover_url (thumbnail image), and rank (the current-position number — "
    "not the rank-change delta). Skip entries that aren't books. Do not "
    "invent fields not present on the page."
)


def fetch_movers(limit: int = 20) -> list[dict]:
    """Return up to `limit` normalized book rows from the M&S page."""
    payload = firecrawl.extract_structured(_URL, schema=_SCHEMA, prompt=_PROMPT)
    raw = payload.get("books", [])[:limit]

    results: list[dict] = []
    for b in raw:
        title = (b.get("title") or "").strip()
        author = (b.get("author") or "").strip()
        asin = (b.get("asin") or "").strip().upper()
        if not title:
            continue
        results.append(
            {
                "title": title,
                "author": author,
                # ASIN for books is usually equal to ISBN-10 for print
                # editions; we still store it under `isbn` so the dedupe
                # logic catches cross-source matches by ID.
                "isbn": asin if len(asin) == 10 else None,
                "asin": asin if len(asin) == 10 else None,
                "description": None,
                "cover_url": b.get("cover_url") or None,
                "source_rank": b.get("rank"),
            }
        )
    return results
