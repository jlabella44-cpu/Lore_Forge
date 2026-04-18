"""Discovery source plugin framework.

Phase B5 of the generalization plan. Before this commit, `run_discovery`
hard-coded a `FETCHERS` dict mapping five book-specific source slugs to
module functions. To support non-book niches, discovery becomes a
plugin registry:

  * Every source implements `DiscoverySource` and registers a slug.
  * The active profile's `sources_config` lists which plugins to run
    and their per-profile config (e.g. an RSS feed URL).
  * `discover.run` iterates the active profile's sources_config and
    dispatches each entry through the registry.

Adding a new source — a web-scraper for a new niche, say — is:
  1. Subclass DiscoverySource, implement fetch(config) → list[dict].
  2. Register via @register_source or the REGISTRY add.
  3. Add the slug to any profile's sources_config.

No code in routers/discover.py needs to change.

The returned dict shape matches what _ingest_hit in discover.py
consumes: {title, author, description, isbn, asin, cover_url,
source_rank?}. New plugins for non-book niches still use `title` and
`author` as the two generic slots — B7 renames those response fields
to match ContentItem's `title` / `subtitle`; for now every plugin
keeps the Books-era names so discover.py stays unchanged.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DiscoverySource(ABC):
    """A pluggable source that returns normalized item dicts.

    Implementations are stateless — one instance per registry slot.
    Per-run configuration (credentials, filter params, feed URLs)
    arrives as the `config` dict, read from the active profile's
    `sources_config[i].config`.
    """

    #: Short identifier. Must match whatever profile.sources_config
    #: entries set as their `plugin_slug`, and whatever lands in
    #: content_item_sources.source for rows this plugin produces.
    slug: str = ""

    @abstractmethod
    def fetch(self, config: dict[str, Any] | None = None) -> list[dict]:
        """Return a list of normalized item dicts. Never raises for a
        configuration problem — raise `RuntimeError` with a clear
        message so `run_discovery` can surface the per-plugin error
        without killing the whole run.

        Contract on the returned dicts:
          * required: title (str), author (str)
          * optional: description, isbn, asin, cover_url, source_rank
        """


# Module-level registry. Populated by side-effect import of each
# `app.sources.<plugin>` module below.
REGISTRY: dict[str, DiscoverySource] = {}


def register(source: DiscoverySource) -> DiscoverySource:
    """Add a source instance to the registry. Idempotent — re-importing
    a plugin module under pytest's fixture churn doesn't double-register.
    """
    if not source.slug:
        raise ValueError(f"{type(source).__name__} must define a non-empty slug")
    REGISTRY[source.slug] = source
    return source


def get(slug: str) -> DiscoverySource | None:
    return REGISTRY.get(slug)


def load_default_plugins() -> None:
    """Import every bundled plugin so their `register(...)` calls fire.

    Safe to call multiple times — each module's register() replaces
    its prior entry with the current class instance, a no-op if the
    module hasn't changed.
    """
    # Book-specific plugins (legacy — map 1:1 to the pre-B5 FETCHERS dict).
    from app.sources import amazon_movers, booktok, goodreads, nyt, reddit_trends  # noqa: F401
    # Generic plugins usable by any profile.
    from app.sources import manual_input, rss_feed  # noqa: F401
