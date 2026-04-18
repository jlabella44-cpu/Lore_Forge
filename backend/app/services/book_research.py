"""Dossier builder — structured research per ContentItem.

Entry point `build_dossier(item)` used by the Books profile pipeline:
  1. Return cached `item.dossier` if populated.
  2. Optionally enrich a thin description via Firecrawl against
     Goodreads (best-effort — falls through on missing key or failure).
  3. Call `llm.generate_book_dossier(...)` to produce the structured
     blob.
  4. Persist onto `item.dossier` (which routes into `item.research`)
     and commit.

The dossier is then threaded into every downstream creative stage so
hooks / scripts / scene prompts cite concrete profile-specific detail
instead of reaching for generic genre vocabulary. B4 extracts the
prompt strings so other profiles can swap in their own research
shape; until then this service is Books-only.
"""
from __future__ import annotations

from sqlalchemy.orm import object_session

from app.config import settings
from app.observability import log_call
from app.services import llm


# Goodreads synopses tend to be ~300-1000 chars. NYT/Amazon fallbacks are
# often one sentence. If the official description is shorter than this,
# try to enrich via Firecrawl so the LLM has something concrete to chew on.
_THIN_DESCRIPTION_CHARS = 300


def build_dossier(item) -> dict:
    """Return a dossier dict for `item`, building (and caching) if needed."""
    if item.dossier:
        return item.dossier

    with log_call(
        "book_research.build_dossier",
        content_item_id=getattr(item, "id", None),
        has_isbn=bool(getattr(item, "isbn", None)),
        desc_len=len(item.description or ""),
    ):
        scraped_extras = _maybe_enrich_via_firecrawl(item)

        dossier = llm.generate_book_dossier(
            title=item.title,
            author=item.subtitle,
            description=item.description,
            scraped_extras=scraped_extras,
        )

    item.dossier = dossier
    session = object_session(item)
    if session is not None:
        session.commit()

    return dossier


def _maybe_enrich_via_firecrawl(item) -> str | None:
    """Best-effort Goodreads scrape. Returns markdown-ish text on success,
    None on any failure (missing key, request error, empty result).

    We don't raise — a thin dossier is strictly better than a failed build,
    so the LLM stage always gets to run.
    """
    desc = item.description or ""
    if len(desc) >= _THIN_DESCRIPTION_CHARS:
        return None
    if not getattr(item, "isbn", None):
        return None
    if not settings.firecrawl_api_key:
        return None

    try:
        from app.services import firecrawl

        # Use search URL so Firecrawl's headless Chrome lands on the book
        # page even when we only have the ISBN.
        url = f"https://www.goodreads.com/search?q={item.isbn}"
        markdown = firecrawl.fetch_markdown(url)
        return markdown or None
    except Exception:
        # Swallow — this is optional enrichment.
        return None
