"""Firecrawl wrapper — Cloudflare-proof web scraping with optional LLM-driven
structured extraction. Talks to their REST API directly so we don't carry a
full SDK dep that tracks a moving target.

Docs: https://docs.firecrawl.dev/features/scrape
Pricing: free tier 500 scrapes/mo; structured extract costs ~1-5 credits
depending on page size.

Two entry points:

    markdown = fetch_markdown(url)                  # cheap, plain markdown
    data     = extract_structured(url, schema, prompt="...")  # Firecrawl LLM extraction

The sources that use this (goodreads, amazon_movers) prefer
`extract_structured` with a JSON Schema — more robust across cosmetic
re-layouts than BS4 selectors.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings

BASE_URL = "https://api.firecrawl.dev/v1"


def _client() -> httpx.Client:
    if not settings.firecrawl_api_key:
        raise RuntimeError("FIRECRAWL_API_KEY is not set")
    return httpx.Client(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {settings.firecrawl_api_key}",
            "Content-Type": "application/json",
        },
        timeout=90.0,
    )


def fetch_markdown(url: str) -> str:
    """Scrape a URL and return the markdown body. Raises RuntimeError on
    non-2xx or Firecrawl-reported failure."""
    with _client() as http:
        resp = http.post("/scrape", json={"url": url, "formats": ["markdown"]})
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(f"Firecrawl scrape failed: {body}")
    return body["data"].get("markdown", "")


def extract_structured(
    url: str,
    *,
    schema: dict[str, Any],
    prompt: str | None = None,
) -> dict[str, Any]:
    """Run Firecrawl's structured extraction against `url` with the given
    JSON Schema. Returns the `extract` payload (matches the schema shape).
    """
    extract: dict[str, Any] = {"schema": schema}
    if prompt:
        extract["prompt"] = prompt

    with _client() as http:
        resp = http.post(
            "/scrape",
            json={"url": url, "formats": ["extract"], "extract": extract},
        )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(f"Firecrawl extract failed: {body}")
    data = body.get("data", {}).get("extract") or {}
    return data
