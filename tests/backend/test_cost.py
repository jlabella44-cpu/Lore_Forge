"""Cost telemetry: pricing math, rollups, and end-to-end attachment."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app.services import cost


# --- record_llm -------------------------------------------------------------


def test_record_llm_computes_opus_cost_from_claude_usage(client):
    # Claude usage: 1000 input, 500 output, 2000 cache-read hit.
    usage = SimpleNamespace(
        input_tokens=1000,
        output_tokens=500,
        cache_read_input_tokens=2000,
        cache_creation_input_tokens=0,
    )
    cost.record_llm(
        call_name="llm.test",
        provider="claude",
        model="claude-opus-4-6",
        usage=usage,
    )

    from app.db import SessionLocal
    from app.models import CostRecord

    db = SessionLocal()
    try:
        row = db.query(CostRecord).first()
        assert row is not None
        assert row.provider == "claude"
        assert row.model == "claude-opus-4-6"
        assert row.input_tokens == 1000
        assert row.output_tokens == 500
        assert row.cache_read_tokens == 2000
        # input: 1000 * $5/M = 0.5¢
        # output: 500 * $25/M = 1.25¢
        # cache read: 2000 * $5/M * 0.1 = 0.1¢
        # total ≈ 1.85¢
        assert abs(row.estimated_cents - 1.85) < 0.01
    finally:
        db.close()


def test_record_llm_handles_openai_usage_shape(client):
    """OpenAI's usage uses prompt_tokens/completion_tokens, not Anthropic's naming."""
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50)
    cost.record_llm(
        call_name="llm.test",
        provider="openai",
        model="gpt-4o-mini",
        usage=usage,
    )

    from app.db import SessionLocal
    from app.models import CostRecord

    db = SessionLocal()
    try:
        row = db.query(CostRecord).order_by(CostRecord.id.desc()).first()
        assert row.input_tokens == 100
        assert row.output_tokens == 50
        # 100 * $0.15/M + 50 * $0.60/M = 0.0015 + 0.003 = 0.0045¢
        assert abs(row.estimated_cents - 0.0045) < 1e-5
    finally:
        db.close()


def test_unknown_model_records_zero_cents_and_warns(client):
    usage = SimpleNamespace(input_tokens=1000, output_tokens=500)
    with patch.object(cost.logger, "warning") as warn:
        cost.record_llm(
            call_name="llm.test",
            provider="claude",
            model="claude-mystery-future-model",
            usage=usage,
        )
    assert warn.called

    from app.db import SessionLocal
    from app.models import CostRecord

    db = SessionLocal()
    try:
        row = db.query(CostRecord).order_by(CostRecord.id.desc()).first()
        assert row.estimated_cents == 0.0
    finally:
        db.close()


# --- non-token providers ----------------------------------------------------


def test_record_tts_computes_per_char(client):
    cost.record_tts(provider="openai", model="tts-1", chars=900)
    from app.db import SessionLocal
    from app.models import CostRecord

    db = SessionLocal()
    try:
        row = db.query(CostRecord).filter(CostRecord.call_name == "tts.synthesize").first()
        assert row is not None
        # 900 chars × $15 / 1M chars = $0.0135 = 1.35¢
        assert abs(row.estimated_cents - 1.35) < 1e-5
    finally:
        db.close()


def test_record_image_per_image(client):
    cost.record_image(provider="wanx", model="wanx2.1-t2i-turbo", count=4)
    from app.db import SessionLocal
    from app.models import CostRecord

    db = SessionLocal()
    try:
        row = db.query(CostRecord).filter(CostRecord.call_name == "images.generate").first()
        # 4 * $0.02 = $0.08 = 8¢
        assert abs(row.estimated_cents - 8.0) < 1e-5
        assert row.units == 4.0
    finally:
        db.close()


def test_record_whisper_per_minute(client):
    cost.record_whisper(provider="openai", model="whisper-1", seconds=90.0)
    from app.db import SessionLocal
    from app.models import CostRecord

    db = SessionLocal()
    try:
        row = db.query(CostRecord).filter(
            CostRecord.call_name == "whisper.transcribe"
        ).first()
        # 90s = 1.5min * $0.006 = $0.009 = 0.9¢
        assert abs(row.estimated_cents - 0.9) < 1e-5
    finally:
        db.close()


# --- ambient package_id via context ----------------------------------------


def test_package_context_attaches_record(client):
    from app import context as app_context

    with app_context.package_context(42):
        cost.record_image(provider="wanx", model="wanx2.1-t2i-turbo", count=1)

    from app.db import SessionLocal
    from app.models import CostRecord

    db = SessionLocal()
    try:
        row = db.query(CostRecord).order_by(CostRecord.id.desc()).first()
        assert row.package_id == 42
    finally:
        db.close()


def test_collect_pending_and_attach(client):
    """generate path: record calls without a package id, attach after creation."""
    with cost.collect_pending() as ids:
        cost.record_image(provider="wanx", model="wanx2.1-t2i-turbo", count=1)
        cost.record_tts(provider="openai", model="tts-1", chars=500)
    assert len(ids) == 2

    cost.attach_pending_to(99, ids)

    from app.db import SessionLocal
    from app.models import CostRecord

    db = SessionLocal()
    try:
        attached = db.query(CostRecord).filter(CostRecord.package_id == 99).count()
        assert attached == 2
    finally:
        db.close()


# --- rollups ---------------------------------------------------------------


def test_summary_last_n_days_groups_by_call_provider_package(client):
    # Seed a fantasy book + a package so per_package can join titles
    from app.db import SessionLocal
    from app.models import ContentItem, ContentPackage

    db = SessionLocal()
    try:
        book = ContentItem(profile_id=1, title="Sample ContentItem", subtitle="Test", status="review")
        db.add(book)
        db.flush()
        pkg = ContentPackage(content_item_id=book.id, revision_number=1, script="x")
        db.add(pkg)
        db.commit()
        pkg_id = pkg.id
    finally:
        db.close()

    cost.record_llm(
        call_name="llm.generate_hooks",
        provider="claude",
        model="claude-opus-4-6",
        usage=SimpleNamespace(input_tokens=100, output_tokens=200),
        package_id=pkg_id,
    )
    cost.record_tts(provider="openai", model="tts-1", chars=1000, package_id=pkg_id)
    cost.record_image(provider="wanx", model="wanx2.1-t2i-turbo", count=5, package_id=pkg_id)
    # Orphan (no package): should count in totals but not per_package.
    cost.record_llm(
        call_name="llm.classify_genre",
        provider="qwen",
        model="qwen-plus",
        usage=SimpleNamespace(input_tokens=50, output_tokens=10),
    )

    summary = cost.summary_last_n_days(30)
    assert summary["days"] == 30
    assert summary["record_count"] == 4
    assert "llm.generate_hooks" in summary["by_call_name"]
    assert summary["by_call_name"]["llm.generate_hooks"]["count"] == 1
    assert "claude" in summary["by_provider"]
    assert "wanx" in summary["by_provider"]

    assert len(summary["per_package"]) == 1
    entry = summary["per_package"][0]
    assert entry["package_id"] == pkg_id
    assert entry["item_title"] == "Sample ContentItem"
    assert entry["cents"] > 0


def test_summary_ignores_rows_outside_window(client):
    from app.db import SessionLocal
    from app.models import CostRecord

    db = SessionLocal()
    try:
        # A record 90 days old
        old = CostRecord(
            created_at=datetime.utcnow() - timedelta(days=90),
            call_name="llm.generate_hooks",
            provider="claude",
            model="claude-opus-4-6",
            estimated_cents=999.0,
        )
        db.add(old)
        db.commit()
    finally:
        db.close()

    summary = cost.summary_last_n_days(30)
    assert summary["record_count"] == 0  # the ancient row is excluded

    full = cost.summary_last_n_days(180)
    assert full["record_count"] == 1
    assert full["total_cents"] == 999.0


def test_per_package_cents_sums(client):
    from app.db import SessionLocal
    from app.models import ContentItem, ContentPackage

    db = SessionLocal()
    try:
        book = ContentItem(profile_id=1, title="X", subtitle="Y", status="review")
        db.add(book)
        db.flush()
        pkg = ContentPackage(content_item_id=book.id, revision_number=1, script="x")
        db.add(pkg)
        db.commit()
        pkg_id = pkg.id
    finally:
        db.close()

    cost.record_image(provider="wanx", model="wanx2.1-t2i-turbo", count=3, package_id=pkg_id)
    cost.record_tts(provider="openai", model="tts-1", chars=1200, package_id=pkg_id)

    total = cost.per_package_cents(pkg_id)
    # 3 images × $0.02 = 6¢; 1200 chars × $15/1M × 100 = 1.8¢ → 7.8¢ total
    assert abs(total - 7.8) < 0.01


# --- endpoint --------------------------------------------------------------


def test_cost_endpoint_returns_summary(client):
    cost.record_image(provider="wanx", model="wanx2.1-t2i-turbo", count=1)
    res = client.get("/analytics/cost")
    assert res.status_code == 200
    body = res.json()
    assert "total_cents" in body
    assert "by_call_name" in body
    assert "by_provider" in body
    assert body["days"] == 30


def test_cost_endpoint_accepts_days_param(client):
    res = client.get("/analytics/cost?days=7")
    assert res.status_code == 200
    assert res.json()["days"] == 7

    # Out-of-range is rejected
    assert client.get("/analytics/cost?days=0").status_code == 422
    assert client.get("/analytics/cost?days=9999").status_code == 422


# --- daily-budget guardrail -------------------------------------------------


def test_assert_under_budget_passes_when_empty(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "cost_daily_budget_cents", 500)
    cost.assert_under_budget()  # no records → 0 spent → passes


def test_assert_under_budget_off_when_zero(client, monkeypatch):
    """Setting the budget to 0 (or negative) disables the guardrail."""
    from app.config import settings

    monkeypatch.setattr(settings, "cost_daily_budget_cents", 0)
    # Drop a bunch of records — should still pass since cap is off.
    cost.record_image(provider="wanx", model="wanx2.1-t2i-turbo", count=1000)
    cost.assert_under_budget()


def test_assert_under_budget_raises_when_exceeded(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "cost_daily_budget_cents", 50)  # 50 cents
    # 3000 Wanx images at 2¢ each = 6000 cents, way past the cap.
    cost.record_image(provider="wanx", model="wanx2.1-t2i-turbo", count=3000)

    import pytest

    with pytest.raises(cost.BudgetExceeded) as exc_info:
        cost.assert_under_budget()
    assert exc_info.value.budget_cents == 50
    assert exc_info.value.spent_cents >= 50


def test_generate_enqueue_returns_429_when_over_budget(client, monkeypatch):
    """The generate router gates on assert_under_budget. Wire it up with a
    real book + over-budget state and verify the 429."""
    from app.config import settings

    monkeypatch.setattr(settings, "cost_daily_budget_cents", 10)

    # Seed a book via the sync path so we have a book_id
    from unittest.mock import patch

    with (
        patch(
            "app.sources.nyt.fetch_bestsellers",
            return_value=[{
                "title": "x", "author": "y", "isbn": "9780000000001",
                "description": "z", "cover_url": None, "source_rank": 1,
            }],
        ),
        patch("app.services.llm.classify_genre", return_value=("fantasy", 0.9)),
    ):
        client.post("/discover/run")

    book_id = client.get("/items").json()[0]["id"]

    # Push spending over the cap
    cost.record_image(provider="wanx", model="wanx2.1-t2i-turbo", count=10)  # 20¢

    # Both sync and async paths should reject with 429
    res_sync = client.post(f"/items/{book_id}/generate", json={})
    assert res_sync.status_code == 429
    assert "budget" in res_sync.json()["detail"].lower()

    res_async = client.post(f"/items/{book_id}/generate?async=true", json={})
    assert res_async.status_code == 429


def test_summary_surfaces_budget_headroom(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "cost_daily_budget_cents", 200)
    cost.record_image(provider="wanx", model="wanx2.1-t2i-turbo", count=25)  # 50¢

    body = client.get("/analytics/cost").json()
    assert body["budget"]["daily_cents"] == 200
    assert abs(body["budget"]["today_cents"] - 50.0) < 0.01
    assert abs(body["budget"]["remaining_cents"] - 150.0) < 0.01


def test_summary_budget_block_empty_when_disabled(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "cost_daily_budget_cents", 0)
    body = client.get("/analytics/cost").json()
    assert body["budget"]["daily_cents"] is None
    assert body["budget"]["remaining_cents"] is None
