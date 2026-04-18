"""RSS/Atom feed source — profile-agnostic.

Pulls items from one or more RSS/Atom feeds declared in the plugin's
config. Each `<item>` / `<entry>` becomes a ContentItem candidate using
  title   → entry title
  author  → feed title (fallback) or <dc:creator>
  description → first N chars of the entry's summary/description
  cover_url   → <media:content url> / <enclosure> / None
  isbn, asin   → None (RSS doesn't surface ISBNs)

Config shape (inside profile.sources_config[].config):
  {
    "feeds": [
      "https://example.com/feed.xml",
      "https://another.site/rss"
    ],
    "max_per_feed": 20          # optional, default 25
  }

The feed URLs are read from the profile — not from env — so different
niches (Films: a trade-press RSS; Recipes: a food-blog RSS) coexist on
one install.

Parsing uses stdlib `xml.etree.ElementTree`; no feedparser dependency.
Handles RSS 2.0 + Atom. Atom's `<entry>` elements have namespaces;
ET.iter() with a wildcard tag skirts around prefixed names without
needing a namespace map.
"""
from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

import httpx

from app.sources.base import DiscoverySource, register


_DEFAULT_MAX = 25


def _local(tag: str) -> str:
    """Strip the `{ns}` prefix Atom inserts on every tag."""
    return tag.rsplit("}", 1)[-1]


def _find_child(el: ET.Element, name: str) -> ET.Element | None:
    for child in el:
        if _local(child.tag) == name:
            return child
    return None


def _text_of(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    txt = (el.text or "").strip()
    return txt or None


def _parse_feed(xml: str, max_items: int) -> list[dict]:
    root = ET.fromstring(xml)
    # RSS: <rss><channel>...<item>; Atom: <feed>...<entry>.
    channel = _find_child(root, "channel") or root
    feed_title = _text_of(_find_child(channel, "title"))

    items: list[dict] = []
    for entry in channel:
        if _local(entry.tag) not in {"item", "entry"}:
            continue
        title = _text_of(_find_child(entry, "title"))
        if not title:
            continue
        author = (
            _text_of(_find_child(entry, "author"))
            or _text_of(_find_child(entry, "creator"))
            or feed_title
            or ""
        )
        description = (
            _text_of(_find_child(entry, "description"))
            or _text_of(_find_child(entry, "summary"))
            or None
        )
        if description and len(description) > 500:
            description = description[:497].rstrip() + "..."

        # Cover: <enclosure url="..."> or <media:content url="...">.
        cover_url: str | None = None
        for child in entry:
            if _local(child.tag) in {"enclosure", "content"} and child.get("url"):
                cover_url = child.get("url")
                break

        items.append(
            {
                "title": title,
                "author": author,
                "description": description,
                "isbn": None,
                "asin": None,
                "cover_url": cover_url,
            }
        )
        if len(items) >= max_items:
            break
    return items


class RssFeedPlugin(DiscoverySource):
    slug = "rss_feed"

    def fetch(self, config: dict[str, Any] | None = None) -> list[dict]:
        cfg = config or {}
        feeds = cfg.get("feeds") or []
        if not feeds:
            raise RuntimeError(
                "rss_feed plugin: profile.sources_config[].config.feeds must "
                "list at least one feed URL"
            )
        max_per_feed = int(cfg.get("max_per_feed") or _DEFAULT_MAX)

        results: list[dict] = []
        for url in feeds:
            resp = httpx.get(url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            # httpx decodes to str using the charset header; fall back
            # to bytes.decode on explicit latin-1 if that returned
            # mojibake (rare).
            results.extend(_parse_feed(resp.text, max_per_feed))
        return results


register(RssFeedPlugin())
