"""Anthropic client. Phase 1 ticket #3 implements these."""
from __future__ import annotations


def classify_genre(title: str, author: str, description: str | None) -> tuple[str, float]:
    """Return (genre, confidence 0..1). Genres: fantasy | scifi | romance | thriller |
    historical_fiction | other."""
    raise NotImplementedError


def generate_package(
    *,
    title: str,
    author: str,
    description: str | None,
    genre: str,
    note: str | None = None,
) -> dict:
    """Return a dict shaped to populate a ContentPackage row:
    {
      script_short, script_long,
      visual_prompts: [str, ...],
      narration,
      titles: {youtube, tiktok, yt_shorts, ig_reels, threads},
      hashtags: {youtube, tiktok, yt_shorts, ig_reels, threads},
      thumbnail_prompt,
    }
    """
    raise NotImplementedError
