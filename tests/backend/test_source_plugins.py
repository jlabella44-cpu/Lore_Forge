"""DiscoverySource ABC, registry, and the two generic plugins."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.sources import base, manual_input, rss_feed


# ---------------------------------------------------------------------------
# Registry + default plugins
# ---------------------------------------------------------------------------


def test_register_requires_slug():
    class NoSlug(base.DiscoverySource):
        def fetch(self, config=None):
            return []

    with pytest.raises(ValueError, match="slug"):
        base.register(NoSlug())


def test_load_default_plugins_populates_every_known_slug():
    base.load_default_plugins()
    for slug in (
        "nyt",
        "goodreads",
        "amazon_movers",
        "booktok",
        "reddit_trends",
        "rss_feed",
        "manual_input",
    ):
        plugin = base.get(slug)
        assert plugin is not None, f"{slug} not registered"
        assert plugin.slug == slug


# ---------------------------------------------------------------------------
# manual_input — pure data passthrough
# ---------------------------------------------------------------------------


def test_manual_input_returns_items_verbatim():
    plugin = manual_input.ManualInputPlugin()
    out = plugin.fetch(
        {
            "items": [
                {"title": "Dune", "author": "Frank Herbert"},
                {
                    "title": "Interstellar",
                    "author": "Christopher Nolan",
                    "description": "A dying Earth.",
                    "cover_url": "https://x/img.jpg",
                },
            ]
        }
    )
    assert len(out) == 2
    assert out[0]["title"] == "Dune"
    assert out[1]["description"] == "A dying Earth."
    assert out[1]["cover_url"] == "https://x/img.jpg"
    # Unset optional keys come back as None, not missing.
    assert out[0]["isbn"] is None


def test_manual_input_rejects_missing_required_fields():
    plugin = manual_input.ManualInputPlugin()
    with pytest.raises(RuntimeError, match="missing title"):
        plugin.fetch({"items": [{"author": "nobody"}]})


def test_manual_input_rejects_non_list_config():
    plugin = manual_input.ManualInputPlugin()
    with pytest.raises(RuntimeError, match="must be a list"):
        plugin.fetch({"items": "not a list"})


def test_manual_input_empty_config_returns_empty():
    plugin = manual_input.ManualInputPlugin()
    assert plugin.fetch({}) == []
    assert plugin.fetch(None) == []


# ---------------------------------------------------------------------------
# rss_feed — XML parsing (no network in tests; patch httpx.get)
# ---------------------------------------------------------------------------


_RSS_2_0 = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>First Post</title>
      <author>Alice</author>
      <description>Short summary.</description>
      <enclosure url="https://x/img1.jpg" />
    </item>
    <item>
      <title>Second Post</title>
      <description>Another one.</description>
    </item>
  </channel>
</rss>
"""


_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Atom Entry</title>
    <summary>Atom summary text.</summary>
  </entry>
</feed>
"""


def _fake_get(xml_body):
    resp = MagicMock()
    resp.text = xml_body
    resp.raise_for_status = MagicMock()
    return resp


def test_rss_feed_parses_rss_2_0():
    plugin = rss_feed.RssFeedPlugin()
    with patch("httpx.get", return_value=_fake_get(_RSS_2_0)):
        out = plugin.fetch({"feeds": ["https://example.com/feed"]})
    assert [i["title"] for i in out] == ["First Post", "Second Post"]
    assert out[0]["author"] == "Alice"
    # Second item has no <author>; falls back to the feed title.
    assert out[1]["author"] == "Example Feed"
    assert out[0]["cover_url"] == "https://x/img1.jpg"
    assert out[1]["cover_url"] is None


def test_rss_feed_parses_atom():
    plugin = rss_feed.RssFeedPlugin()
    with patch("httpx.get", return_value=_fake_get(_ATOM)):
        out = plugin.fetch({"feeds": ["https://example.com/atom"]})
    assert len(out) == 1
    assert out[0]["title"] == "Atom Entry"
    assert out[0]["description"] == "Atom summary text."
    assert out[0]["author"] == "Atom Feed"


def test_rss_feed_respects_max_per_feed():
    body = "".join(
        f"<item><title>Post {i}</title></item>" for i in range(50)
    )
    xml = f"<rss><channel><title>F</title>{body}</channel></rss>"
    plugin = rss_feed.RssFeedPlugin()
    with patch("httpx.get", return_value=_fake_get(xml)):
        out = plugin.fetch(
            {"feeds": ["https://example.com"], "max_per_feed": 5}
        )
    assert len(out) == 5


def test_rss_feed_truncates_long_descriptions():
    long_desc = "x" * 1000
    xml = (
        f"<rss><channel><title>F</title>"
        f"<item><title>T</title><description>{long_desc}</description></item>"
        f"</channel></rss>"
    )
    plugin = rss_feed.RssFeedPlugin()
    with patch("httpx.get", return_value=_fake_get(xml)):
        out = plugin.fetch({"feeds": ["https://example.com"]})
    assert len(out[0]["description"]) <= 500
    assert out[0]["description"].endswith("...")


def test_rss_feed_missing_feeds_raises():
    plugin = rss_feed.RssFeedPlugin()
    with pytest.raises(RuntimeError, match="feeds"):
        plugin.fetch({})


# ---------------------------------------------------------------------------
# discover.run pulls plugin config from the active profile
# ---------------------------------------------------------------------------


def test_discover_passes_per_plugin_config_from_profile(client, monkeypatch):
    """A Films-style profile with rss_feed as its source and its own
    feeds list should end up calling RssFeedPlugin.fetch with that
    exact config, not the book-profile default.
    """
    from app.config import settings
    from app.db import SessionLocal
    from app.models import Profile

    # Drop the Books profile off active, add Films with rss_feed.
    db = SessionLocal()
    try:
        books = db.query(Profile).filter(Profile.slug == "books").one()
        books.active = False
        db.add(
            Profile(
                slug="films",
                name="Films",
                entity_label="Film",
                active=True,
                sources_config=[
                    {
                        "plugin_slug": "rss_feed",
                        "config": {"feeds": ["https://indie-films.example/feed"]},
                    }
                ],
                prompts={},
                taxonomy=[],
                cta_fields=[],
                render_tones={},
            )
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(settings, "sources_enabled", "rss_feed")

    captured = {}

    def _fake_fetch(self, config=None):
        captured["config"] = config
        return []

    with patch("app.sources.rss_feed.RssFeedPlugin.fetch", _fake_fetch):
        res = client.post("/discover/run")

    assert res.status_code == 200
    assert captured["config"] == {"feeds": ["https://indie-films.example/feed"]}
