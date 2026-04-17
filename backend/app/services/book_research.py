"""Book dossier builder — structured research per book.

`build_dossier(book)` is the single entry point:
  1. If `book.dossier` is already populated, return it (cache hit — no
     LLM call).
  2. Otherwise, optionally enrich a thin description by scraping Goodreads
     via Firecrawl (best-effort — falls through on missing key or failure).
  3. Call `llm.generate_book_dossier(...)` to produce the structured blob.
  4. Persist onto `book.dossier` and commit.

The dossier is then threaded into every downstream creative stage so
hooks / scripts / scene prompts cite concrete book-specific detail instead
of reaching for generic genre vocabulary.
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


def build_dossier(book) -> dict:
    """Return a dossier dict for `book`, building (and caching) if needed."""
    if book.dossier:
        return book.dossier

    with log_call(
        "book_research.build_dossier",
        book_id=getattr(book, "id", None),
        has_isbn=bool(getattr(book, "isbn", None)),
        desc_len=len(book.description or ""),
    ):
        scraped_extras = _maybe_enrich_via_firecrawl(book)

        dossier = llm.generate_book_dossier(
            title=book.title,
            author=book.author,
            description=book.description,
            scraped_extras=scraped_extras,
        )

    book.dossier = dossier
    session = object_session(book)
    if session is not None:
        session.commit()

    return dossier


def _maybe_enrich_via_firecrawl(book) -> str | None:
    """Best-effort Goodreads scrape. Returns markdown-ish text on success,
    None on any failure (missing key, request error, empty result).

    We don't raise — a thin dossier is strictly better than a failed build,
    so the LLM stage always gets to run.
    """
    desc = book.description or ""
    if len(desc) >= _THIN_DESCRIPTION_CHARS:
        return None
    if not getattr(book, "isbn", None):
        return None
    if not settings.firecrawl_api_key:
        return None

    try:
        from app.services import firecrawl

        # Use search URL so Firecrawl's headless Chrome lands on the book
        # page even when we only have the ISBN.
        url = f"https://www.goodreads.com/search?q={book.isbn}"
        markdown = firecrawl.fetch_markdown(url)
        return markdown or None
    except Exception:
        # Swallow — this is optional enrichment.
        return None
