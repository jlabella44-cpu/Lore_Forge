"""Analytics endpoints.

Phase 2: per-call spend. Phase 3: video performance (views, CTR, revenue).
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import cost

router = APIRouter()


@router.get("/cost")
def cost_summary(days: int = Query(30, ge=1, le=365)) -> dict:
    """Rolling-window spend grouped by call, provider, and package.

    `days` defaults to 30. Returns dollar totals and per-package entries
    joined to the book title so the UI can list them without a follow-up
    request.
    """
    return cost.summary_last_n_days(days=days)
