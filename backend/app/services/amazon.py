"""Amazon affiliate link construction — Phase 1.

We build the URL from ASIN + associate tag. ASIN lookup by ISBN uses a separate
provider (ISBNdb free tier or OpenLibrary) — see Phase 1 ticket #4.
"""
from __future__ import annotations

from app.config import settings


def build_affiliate_url(asin: str) -> str:
    tag = settings.amazon_associate_tag
    if not tag:
        raise RuntimeError("AMAZON_ASSOCIATE_TAG is not set")
    return f"https://www.amazon.com/dp/{asin}/?tag={tag}"


def lookup_asin(isbn: str) -> str | None:
    """Phase 1 ticket #4: resolve ISBN → ASIN via ISBNdb or OpenLibrary."""
    raise NotImplementedError


def build_bookshop_url(isbn: str) -> str:
    affiliate_id = settings.bookshop_affiliate_id
    if not affiliate_id:
        raise RuntimeError("BOOKSHOP_AFFILIATE_ID is not set")
    return f"https://bookshop.org/a/{affiliate_id}/{isbn}"
