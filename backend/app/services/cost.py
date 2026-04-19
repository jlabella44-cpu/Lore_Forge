"""Per-call spend tracking.

Every external provider we pay for funnels through one of the `record_*`
entry points in this module. Each writes a CostRecord row with the
best-effort `estimated_cents` computed from the pricing table below.

Design rules:

- Never fail the caller if pricing is unknown or the write errors —
  telemetry is not on the critical path. Unrecognized (provider, model)
  pairs log a warning and record 0 cents so the row still exists for
  auditing.
- Don't block the request on recording. The write is cheap (single
  insert) so we do it inline, but wrap it in try/except.
- Published rates are baked into the PRICING dict so they're grep-able
  and reviewable alongside the code. Claude prompt caching is honored:
  cache reads bill at 0.1x the input rate, cache writes at 1.25x.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta
from typing import Any, Iterator

from app import context as app_context
from app import db as _db_module
from app.clock import utc_now
from app.models import ContentItem, ContentPackage, CostRecord
from app.observability import get_logger

logger = get_logger("cost")

# Dollars per million tokens (_per_m) or per unit (_per_char, _per_image,
# _per_minute). Numbers sourced from the public Anthropic / OpenAI /
# Dashscope rate cards as of 2026-Q2. Claude cache-hit reads bill at
# 0.1x input; cache writes at 1.25x — both computed in record_llm.
PRICING: dict[tuple[str, str], dict[str, float]] = {
    ("claude", "claude-opus-4-6"):  {"input_per_m": 5.00, "output_per_m": 25.00},
    ("claude", "claude-sonnet-4-6"):{"input_per_m": 3.00, "output_per_m": 15.00},
    ("claude", "claude-haiku-4-5"): {"input_per_m": 1.00, "output_per_m":  5.00},
    ("openai", "gpt-4o"):           {"input_per_m": 2.50, "output_per_m": 10.00},
    ("openai", "gpt-4o-mini"):      {"input_per_m": 0.15, "output_per_m":  0.60},
    ("openai", "tts-1"):            {"per_char": 15.00 / 1_000_000},
    ("openai", "tts-1-hd"):         {"per_char": 30.00 / 1_000_000},
    ("openai", "whisper-1"):        {"per_minute": 0.006},
    ("qwen",   "qwen-plus"):        {"input_per_m": 0.30, "output_per_m":  0.90},
    ("qwen",   "qwen-max"):         {"input_per_m": 3.00, "output_per_m":  9.00},
    ("wanx",   "wanx2.1-t2i-turbo"):{"per_image": 0.02},
    ("wanx",   "wanx2.1-t2i-plus"): {"per_image": 0.04},
}


# ---------------------------------------------------------------------------
# public recorders
# ---------------------------------------------------------------------------

def record_llm(
    *,
    call_name: str,
    provider: str,
    model: str,
    usage: Any,
    package_id: int | None = None,
) -> None:
    """Record a chat-model call. `usage` is either:
      * an Anthropic usage object with input_tokens/output_tokens/
        cache_read_input_tokens/cache_creation_input_tokens, or
      * an OpenAI CompletionUsage with prompt_tokens/completion_tokens.
    """
    input_tokens, output_tokens, cache_read, cache_write = _extract_tokens(usage)
    rate = PRICING.get((provider, model))
    if rate is None:
        _warn_unknown(provider, model)
        cents = 0.0
    else:
        input_cost = (
            (input_tokens or 0) * rate.get("input_per_m", 0.0) / 1_000_000
            + (cache_read or 0) * rate.get("input_per_m", 0.0) * 0.1 / 1_000_000
            + (cache_write or 0) * rate.get("input_per_m", 0.0) * 1.25 / 1_000_000
        )
        output_cost = (output_tokens or 0) * rate.get("output_per_m", 0.0) / 1_000_000
        cents = (input_cost + output_cost) * 100

    _write(
        call_name=call_name,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        units=None,
        estimated_cents=cents,
        package_id=package_id,
    )


def record_tts(
    *,
    provider: str,
    model: str,
    chars: int,
    package_id: int | None = None,
) -> None:
    rate = PRICING.get((provider, model))
    cents = (chars * rate["per_char"] * 100) if rate and "per_char" in rate else 0.0
    if rate is None or "per_char" not in rate:
        _warn_unknown(provider, model)

    _write(
        call_name="tts.synthesize",
        provider=provider,
        model=model,
        input_tokens=None,
        output_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
        units=float(chars),
        estimated_cents=cents,
        package_id=package_id,
    )


def record_image(
    *,
    provider: str,
    model: str,
    count: int = 1,
    package_id: int | None = None,
) -> None:
    rate = PRICING.get((provider, model))
    cents = (count * rate["per_image"] * 100) if rate and "per_image" in rate else 0.0
    if rate is None or "per_image" not in rate:
        _warn_unknown(provider, model)

    _write(
        call_name="images.generate",
        provider=provider,
        model=model,
        input_tokens=None,
        output_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
        units=float(count),
        estimated_cents=cents,
        package_id=package_id,
    )


def record_whisper(
    *,
    provider: str,
    model: str,
    seconds: float,
    package_id: int | None = None,
) -> None:
    rate = PRICING.get((provider, model))
    minutes = max(seconds / 60.0, 0.0)
    cents = (minutes * rate["per_minute"] * 100) if rate and "per_minute" in rate else 0.0
    if rate is None or "per_minute" not in rate:
        _warn_unknown(provider, model)

    _write(
        call_name="whisper.transcribe",
        provider=provider,
        model=model,
        input_tokens=None,
        output_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
        units=seconds,
        estimated_cents=cents,
        package_id=package_id,
    )


# ---------------------------------------------------------------------------
# rollups used by GET /analytics/cost
# ---------------------------------------------------------------------------

def spend_last_24h_cents() -> float:
    """Rolling 24-hour sum, used by the daily-budget guardrail.

    Separate from `summary_last_n_days(1)` so it can be called on every
    enqueue without paying for the full grouping pass.
    """
    since = utc_now() - timedelta(hours=24)
    db = _db_module.SessionLocal()
    try:
        rows = (
            db.query(CostRecord.estimated_cents)
            .filter(CostRecord.created_at >= since)
            .all()
        )
        return round(sum(r[0] for r in rows), 2)
    finally:
        db.close()


class BudgetExceeded(RuntimeError):
    """Raised when the rolling 24h spend would push past the daily cap."""

    def __init__(self, spent_cents: float, budget_cents: int) -> None:
        self.spent_cents = spent_cents
        self.budget_cents = budget_cents
        super().__init__(
            f"Daily cost budget exceeded: ${spent_cents / 100:.2f} spent "
            f"in the last 24h, budget is ${budget_cents / 100:.2f}. "
            "Raise COST_DAILY_BUDGET_CENTS or set it to 0 to disable."
        )


def assert_under_budget() -> None:
    """Raise BudgetExceeded if the rolling 24h spend meets/exceeds the cap.

    Routers call this before enqueueing expensive work. Budget ≤ 0 means
    the guardrail is off (useful for dev / testing).
    """
    from app.config import settings

    budget = settings.cost_daily_budget_cents
    if budget is None or budget <= 0:
        return
    spent = spend_last_24h_cents()
    if spent >= budget:
        raise BudgetExceeded(spent, budget)


def per_package_cents(package_id: int) -> float:
    db = _db_module.SessionLocal()
    try:
        total = (
            db.query(CostRecord)
            .filter(CostRecord.package_id == package_id)
            .with_entities(CostRecord.estimated_cents)
            .all()
        )
        return round(sum(row[0] for row in total), 2)
    finally:
        db.close()


def summary_last_n_days(days: int = 30) -> dict:
    since = utc_now() - timedelta(days=days)
    db = _db_module.SessionLocal()
    try:
        rows = (
            db.query(CostRecord)
            .filter(CostRecord.created_at >= since)
            .all()
        )
        by_call: dict[str, dict] = {}
        by_provider: dict[str, float] = {}
        total = 0.0
        for r in rows:
            total += r.estimated_cents
            call_bucket = by_call.setdefault(r.call_name, {"count": 0, "cents": 0.0})
            call_bucket["count"] += 1
            call_bucket["cents"] += r.estimated_cents
            by_provider[r.provider] = by_provider.get(r.provider, 0.0) + r.estimated_cents

        # Per-package rollup — join titles for the UI.
        package_totals: dict[int, float] = {}
        for r in rows:
            if r.package_id is None:
                continue
            package_totals[r.package_id] = (
                package_totals.get(r.package_id, 0.0) + r.estimated_cents
            )

        per_package = []
        if package_totals:
            rows_ = (
                db.query(ContentPackage, ContentItem)
                .join(ContentItem, ContentItem.id == ContentPackage.content_item_id)
                .filter(ContentPackage.id.in_(package_totals.keys()))
                .all()
            )
            for pkg, item in rows_:
                per_package.append(
                    {
                        "package_id": pkg.id,
                        "item_id": item.id,
                        "item_title": item.title,
                        "revision_number": pkg.revision_number,
                        "cents": round(package_totals[pkg.id], 2),
                    }
                )
            per_package.sort(key=lambda r: r["cents"], reverse=True)

        from app.config import settings

        budget = settings.cost_daily_budget_cents
        today_cents = spend_last_24h_cents()

        return {
            "since": since.isoformat(),
            "days": days,
            "total_cents": round(total, 2),
            "total_usd": f"{total / 100:.2f}",
            "by_call_name": {
                k: {"count": v["count"], "cents": round(v["cents"], 2)}
                for k, v in by_call.items()
            },
            "by_provider": {k: round(v, 2) for k, v in by_provider.items()},
            "per_package": per_package,
            "record_count": len(rows),
            "budget": {
                "daily_cents": budget if budget and budget > 0 else None,
                "today_cents": today_cents,
                "remaining_cents": (
                    max(0.0, budget - today_cents)
                    if budget and budget > 0
                    else None
                ),
            },
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _extract_tokens(usage: Any) -> tuple[int | None, int | None, int | None, int | None]:
    """Best-effort pull from an Anthropic/OpenAI usage object. Anything we
    can't read just comes back None — the row still gets written."""
    input_tokens = _get(usage, "input_tokens", "prompt_tokens")
    output_tokens = _get(usage, "output_tokens", "completion_tokens")
    cache_read = _get(usage, "cache_read_input_tokens")
    cache_write = _get(usage, "cache_creation_input_tokens")
    return input_tokens, output_tokens, cache_read, cache_write


def _get(obj: Any, *names: str) -> int | None:
    for name in names:
        v = getattr(obj, name, None)
        if v is None and isinstance(obj, dict):
            v = obj.get(name)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
    return None


def _warn_unknown(provider: str, model: str) -> None:
    logger.warning(
        "cost.unknown_rate provider=%s model=%s — recording 0 cents",
        provider,
        model,
    )


# Records created inside a `collect_pending()` block get their ids pushed
# onto this list so a caller that can't supply package_id up front (e.g.
# generate_package — the package doesn't exist yet) can attach them all
# at once after the package is persisted.
_pending_record_ids: ContextVar[list[int] | None] = ContextVar(
    "lore_cost_pending_ids", default=None
)


@contextmanager
def collect_pending() -> Iterator[list[int]]:
    """Buffer cost-record ids created inside this block. Used by the
    generate router to attach records to the package after it's been
    created."""
    ids: list[int] = []
    token = _pending_record_ids.set(ids)
    try:
        yield ids
    finally:
        _pending_record_ids.reset(token)


def attach_pending_to(package_id: int, ids: list[int]) -> None:
    """Link buffered records to a newly-created package."""
    if not ids:
        return
    db = _db_module.SessionLocal()
    try:
        (
            db.query(CostRecord)
            .filter(CostRecord.id.in_(ids))
            .update(
                {CostRecord.package_id: package_id},
                synchronize_session=False,
            )
        )
        db.commit()
    except Exception:
        logger.exception("cost.attach_pending_to failed — swallowing")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _write(**fields: Any) -> None:
    """Insert a CostRecord, attaching the ambient package_id if the caller
    didn't supply one. Any write failure is swallowed after logging so
    telemetry never takes the main flow down."""
    if fields.get("package_id") is None:
        fields["package_id"] = app_context.get_package_id()

    db = _db_module.SessionLocal()
    try:
        row = CostRecord(**fields)
        db.add(row)
        db.commit()
        db.refresh(row)
        pending = _pending_record_ids.get()
        if pending is not None and row.id is not None:
            pending.append(row.id)
    except Exception:
        logger.exception("cost.write failed — swallowing to protect caller")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()
