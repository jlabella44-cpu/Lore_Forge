"""Placeholder — real cases land with Phase 2 scoring implementation."""
import pytest


@pytest.mark.skip(reason="Phase 2 — scoring.score_book not implemented yet")
def test_score_book_weights():
    from app.scoring import score_book

    assert score_book([("nyt", 1.0), ("reddit", 1.0)]) == pytest.approx(3.5)
