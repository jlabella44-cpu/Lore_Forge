"""Cross-source scoring."""
from datetime import timedelta

from app.scoring import (
    SOURCE_WEIGHTS,
    is_priority,
    recency_multiplier,
    score_book,
)


def test_score_single_source_full_recency():
    assert score_book([("nyt", 1.0)]) == 2.0
    assert score_book([("booktok", 1.0)]) == 3.0


def test_score_accumulates_across_sources():
    # NYT + BookTok + Reddit, all fresh
    hits = [("nyt", 1.0), ("booktok", 1.0), ("reddit", 1.0)]
    # 2.0 + 3.0 + 1.5 = 6.5
    assert score_book(hits) == 6.5


def test_score_applies_recency_multiplier():
    # Half-recency BookTok + fresh NYT = (3.0 * 0.5) + (2.0 * 1.0) = 3.5
    assert score_book([("booktok", 0.5), ("nyt", 1.0)]) == 3.5


def test_score_clamps_recency_to_unit_range():
    # Out-of-range values are clamped.
    assert score_book([("nyt", 5.0)]) == 2.0
    assert score_book([("nyt", -1.0)]) == 0.0


def test_score_ignores_unknown_sources():
    assert score_book([("nyt", 1.0), ("unknown_source", 1.0)]) == 2.0


def test_recency_multiplier_decay():
    # Fresh → 1.0
    assert recency_multiplier(timedelta(seconds=0)) == 1.0
    # One half-life → 0.5
    assert abs(recency_multiplier(timedelta(days=14)) - 0.5) < 1e-6
    # Two half-lives → 0.25
    assert abs(recency_multiplier(timedelta(days=28)) - 0.25) < 1e-6
    # Negative age → 1.0 (clock skew tolerant)
    assert recency_multiplier(timedelta(seconds=-10)) == 1.0


def test_recency_multiplier_custom_half_life():
    assert abs(recency_multiplier(timedelta(days=7), half_life=timedelta(days=7)) - 0.5) < 1e-6


def test_is_priority_requires_score_and_source_breadth():
    # Priority = ≥7 points AND ≥3 sources
    assert is_priority(7.0, 3) is True
    assert is_priority(8.0, 3) is True
    # Too few points
    assert is_priority(6.9, 5) is False
    # Too few sources
    assert is_priority(10.0, 2) is False


def test_weight_table_matches_prd_spec():
    assert SOURCE_WEIGHTS == {
        "booktok": 3.0,
        "amazon_movers": 2.5,
        "goodreads": 2.0,
        "nyt": 2.0,
        "reddit": 1.5,
    }
