"""#BookTok TikTok trends — deferred.

Intentionally not implemented. TikTok's public surface (the /tag/booktok
landing page and individual video pages) only exposes video URLs, captions,
and engagement metrics. Extracting *which book* a video is about requires
one of:

  - NLP over captions + top-pinned comments (noisy, ~60% accuracy on spot
    checks).
  - A dedicated TikTok data provider (Bright Data's TikTok Scraper, Apify's
    TikTok actor, etc.) that surfaces structured book metadata — paid.
  - The official TikTok Research API (requires academic/business approval;
    gated, slow turnaround).

Firecrawl can scrape the tag page but TikTok actively blocks scraping and
the extracted "books" would need a second NLP pass anyway. Either of the
above is a better investment than a brittle Firecrawl path here.

Leave this returning [] so the discover fan-out stays happy; revisit when
one of the routes above is chosen.
"""
from __future__ import annotations


def fetch_booktok() -> list[dict]:
    return []
