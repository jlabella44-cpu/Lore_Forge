"""Manual input source — profile-agnostic.

Returns exactly the items the user pasted into the profile's config.
No network calls, no scraping. The dashboard (B6) ends up writing to
this plugin's config whenever the user taps an "Add items manually"
affordance.

Config shape (inside profile.sources_config[].config):
  {
    "items": [
      {
        "title": "Interstellar",
        "author": "Christopher Nolan",          # generic secondary label
        "description": "A dying Earth...",      # optional
        "cover_url": "https://...",              # optional
        "isbn": null,                           # optional (Books only)
        "asin": null                            # optional (Books only)
      },
      ...
    ]
  }

`title` + `author` are required on every item; everything else is
optional and passes straight through to the ingest stage.
"""
from __future__ import annotations

from typing import Any

from app.sources.base import DiscoverySource, register


class ManualInputPlugin(DiscoverySource):
    slug = "manual_input"

    def fetch(self, config: dict[str, Any] | None = None) -> list[dict]:
        cfg = config or {}
        raw = cfg.get("items") or []
        if not isinstance(raw, list):
            raise RuntimeError(
                "manual_input plugin: config.items must be a list of item "
                f"dicts (got {type(raw).__name__})"
            )

        out: list[dict] = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                raise RuntimeError(
                    f"manual_input plugin: items[{i}] must be an object"
                )
            title = (item.get("title") or "").strip()
            author = (item.get("author") or "").strip()
            if not title or not author:
                raise RuntimeError(
                    f"manual_input plugin: items[{i}] missing title or author"
                )
            out.append(
                {
                    "title": title,
                    "author": author,
                    "description": item.get("description") or None,
                    "cover_url": item.get("cover_url") or None,
                    "isbn": item.get("isbn") or None,
                    "asin": item.get("asin") or None,
                }
            )
        return out


register(ManualInputPlugin())
