"""Cross-source scoring — Phase 2.

Per-source weights (PRD §3):
    booktok: 3.0         (highest velocity signal)
    amazon_movers: 2.5   (purchase intent)
    goodreads: 2.0
    nyt: 2.0
    reddit: 1.5

Final score = sum of (weight × recency_multiplier) across all source hits.

`recency_multiplier` is 1.0 for a fresh hit, decaying toward 0.0 as the hit
ages. Default decay: 14 days = ~0.5; callers can pass their own decay window.

Priority Queue (flagged for fast-track generation): score ≥ 7 AND hits from
at least 3 distinct sources.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

SOURCE_WEIGHTS: dict[str, float] = {
    "booktok": 3.0,
    "amazon_movers": 2.5,
    "goodreads": 2.0,
    "nyt": 2.0,
    "reddit": 1.5,
}

# Default: a hit 14 days old counts half as much as a fresh hit.
DEFAULT_HALF_LIFE_DAYS = 14.0


def score_book(source_hits: Iterable[tuple[str, float]]) -> float:
    """Sum weighted points for (source_name, recency_multiplier) pairs.

    `recency_multiplier` must be in [0.0, 1.0]. Unknown sources contribute 0.
    """
    total = 0.0
    for source, recency in source_hits:
        weight = SOURCE_WEIGHTS.get(source, 0.0)
        total += weight * max(0.0, min(1.0, recency))
    return round(total, 3)


def recency_multiplier(
    age: timedelta,
    half_life: timedelta | None = None,
) -> float:
    """Exponential decay. Fresh = 1.0, one half-life = 0.5, etc."""
    if age.total_seconds() <= 0:
        return 1.0
    hl = (half_life or timedelta(days=DEFAULT_HALF_LIFE_DAYS)).total_seconds()
    return 0.5 ** (age.total_seconds() / hl)


def recency_multiplier_from(
    discovered_at: datetime,
    now: datetime | None = None,
) -> float:
    now = now or datetime.utcnow()
    return recency_multiplier(now - discovered_at)


def is_priority(score: float, source_count: int) -> bool:
    """PRD §3 priority-queue rule: ≥7 points from ≥3 distinct sources."""
    return score >= 7.0 and source_count >= 3
