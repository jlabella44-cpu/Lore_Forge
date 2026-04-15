"""Cross-source scoring — Phase 2.

Per-source weights (from PRD §3):
    booktok: 3.0         (highest velocity signal)
    amazon_movers: 2.5   (purchase intent)
    goodreads: 2.0
    nyt: 2.0
    reddit: 1.5

Final score = sum of weighted source points × recency multiplier.
Priority Queue: score >= 7 AND sources >= 3.
"""
from __future__ import annotations

SOURCE_WEIGHTS: dict[str, float] = {
    "booktok": 3.0,
    "amazon_movers": 2.5,
    "goodreads": 2.0,
    "nyt": 2.0,
    "reddit": 1.5,
}


def score_book(source_hits: list[tuple[str, float]]) -> float:
    """source_hits = [(source_name, recency_multiplier), ...]"""
    raise NotImplementedError
