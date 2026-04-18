"""Reddit r/Fantasy + r/scifi hot posts — free public JSON endpoint, no OAuth.

We scan the top posts of the configured subreddits and pull out book-mention
signal. A full implementation would NLP-extract titles from post bodies; for
Phase 2 we use a lightweight heuristic: posts whose title matches
`"Title" by Author` / `Title - Author` patterns are ingested directly.

Unparseable posts are skipped — Reddit is high-noise and we'd rather miss a
book than create a Book row from a shitpost.
"""
from __future__ import annotations

import re

import httpx

from app.config import settings

SUBREDDITS = ["Fantasy", "scifi"]
POSTS_PER_SUB = 25

# Trailing separator can be any of : , - — – so comment/rant tails don't
# break the parse. Author capture is non-greedy and stops at that separator.
_TAIL = r"(?:\s*[:,\-—–].*)?$"

_BOOK_PATTERNS = [
    # "Title" by Author ...
    re.compile(rf'^"([^"]{{2,120}})"\s+by\s+([\w .,\'\-&]+?){_TAIL}', re.IGNORECASE),
    # Title by Author ...
    re.compile(rf"^(.{{2,120}}?)\s+by\s+([A-Z][\w .,\'\-&]+?){_TAIL}"),
    # Title - Author ... / Title — Author ...
    re.compile(rf"^(.{{2,120}}?)\s[\-—–]\s([A-Z][\w .,\'\-&]+?){_TAIL}"),
]


def fetch_reddit_trends() -> list[dict]:
    """Return normalized book rows inferred from r/Fantasy + r/scifi hot."""
    ua = settings.reddit_user_agent or "lore-forge/0.1 (book-discovery bot)"
    results: list[dict] = []
    seen: set[tuple[str, str]] = set()

    with httpx.Client(headers={"User-Agent": ua}, timeout=30.0) as http:
        for sub in SUBREDDITS:
            resp = http.get(
                f"https://www.reddit.com/r/{sub}/hot.json",
                params={"limit": POSTS_PER_SUB, "raw_json": 1},
            )
            resp.raise_for_status()
            for pos, child in enumerate(resp.json().get("data", {}).get("children", [])):
                post = child.get("data", {})
                title = (post.get("title") or "").strip()
                score = post.get("score", 0)
                parsed = _extract_book(title)
                if parsed is None:
                    continue
                book_title, author = parsed
                key = (book_title.lower(), author.lower())
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    {
                        "title": book_title,
                        "author": author,
                        "isbn": None,
                        "description": post.get("selftext") or None,
                        "cover_url": None,
                        "source_rank": pos + 1,
                        # Not persisted directly, but handy for future scoring
                        # by popularity within Reddit.
                        "_reddit_score": score,
                        "_subreddit": sub,
                    }
                )
    return results


def _extract_book(title: str) -> tuple[str, str] | None:
    """Return (book_title, author) if the post title looks like a
    recommendation; None otherwise."""
    stripped = title.strip().strip("[](){}")
    for pat in _BOOK_PATTERNS:
        m = pat.match(stripped)
        if m:
            bt = m.group(1).strip().strip('"')
            au = m.group(2).strip().strip(".,")
            if len(bt) >= 2 and len(au) >= 2 and " " in au:
                return bt, au
    return None


from app.sources.base import DiscoverySource, register  # noqa: E402


class RedditTrendsPlugin(DiscoverySource):
    # Slug matches both the migration-0009 seed and the module name.
    # Pre-B5 FETCHERS used "reddit" — callers with SOURCES_ENABLED=reddit
    # will hit the "unknown source" branch after this change and need
    # to update their env to SOURCES_ENABLED=reddit_trends. Single-user
    # dev setup; no broad deploys to migrate.
    slug = "reddit_trends"

    def fetch(self, config=None) -> list[dict]:
        return fetch_reddit_trends()


register(RedditTrendsPlugin())
