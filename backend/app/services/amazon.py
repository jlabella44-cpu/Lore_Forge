"""Amazon + Bookshop.org affiliate link helpers — Phase 1 ticket #4.

Amazon affiliate URLs for books work with the ASIN *or* ISBN-10 — Amazon
redirects. We try, in order:

1. ISBNdb `/book/{isbn}` if `ISBNDB_API_KEY` is set (paid, most accurate).
2. Algorithmic ISBN-13 → ISBN-10 conversion. Covers virtually all print books
   (ASIN == ISBN-10 for pre-Kindle editions and most modern print editions).

OpenLibrary was considered but doesn't expose ASIN — skipped.
"""
from __future__ import annotations

import httpx

from app.config import settings


# ---- affiliate URL builders -------------------------------------------------

def build_affiliate_url(asin_or_isbn10: str) -> str:
    tag = settings.amazon_associate_tag
    if not tag:
        raise RuntimeError("AMAZON_ASSOCIATE_TAG is not set")
    return f"https://www.amazon.com/dp/{asin_or_isbn10}/?tag={tag}"


def build_bookshop_url(isbn: str) -> str:
    affiliate_id = settings.bookshop_affiliate_id
    if not affiliate_id:
        raise RuntimeError("BOOKSHOP_AFFILIATE_ID is not set")
    return f"https://bookshop.org/a/{affiliate_id}/{isbn}"


# ---- ISBN → ASIN lookup -----------------------------------------------------

def lookup_asin(isbn: str) -> str | None:
    """Return an Amazon-usable identifier for a given ISBN (10 or 13).

    If ISBNdb is configured, prefer its authoritative lookup. Otherwise derive
    the ISBN-10 algorithmically — valid for the /dp/ URL pattern.
    """
    if settings.isbndb_api_key:
        try:
            asin = _isbndb_lookup(isbn)
            if asin:
                return asin
        except Exception:
            pass  # fall through to algorithmic derivation
    return isbn13_to_isbn10(isbn)


def _isbndb_lookup(isbn: str) -> str | None:
    resp = httpx.get(
        f"https://api2.isbndb.com/book/{isbn}",
        headers={"Authorization": settings.isbndb_api_key},
        timeout=10.0,
    )
    if resp.status_code != 200:
        return None
    book = resp.json().get("book", {})
    return book.get("isbn10") or book.get("isbn")


def isbn13_to_isbn10(isbn: str) -> str | None:
    """Convert a 978-prefixed ISBN-13 to ISBN-10. Returns the input unchanged
    if already a 10-digit ISBN. Returns None for 979-prefixed ISBN-13s (no
    ISBN-10 exists for those)."""
    digits = isbn.replace("-", "").replace(" ", "")
    if len(digits) == 10:
        return digits
    if len(digits) != 13 or not digits.startswith("978"):
        return None
    core = digits[3:12]  # 9 digits after the "978" prefix
    weighted = sum((i + 1) * int(d) for i, d in enumerate(core))
    check = weighted % 11
    check_char = "X" if check == 10 else str(check)
    return core + check_char
