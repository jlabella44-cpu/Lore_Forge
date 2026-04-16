# Followups

Short-lived punch list of known technical debt / later PRs. Delete items as
they land; don't let this turn into a design doc.

## Schema

- **Two-DB divergence (fixed).** `backend/lore_forge.sqlite` (real data) and
  `db/lore_forge.sqlite` (alembic-only scaffold) were never the same file
  because `DATABASE_URL=sqlite:///./lore_forge.sqlite` was relative to the
  cwd of whoever ran it. Short-term fix (runs locally, not in CI): `cd
  backend && alembic stamp 0004_cost_records && alembic upgrade head`.
  Root-cause fix landed in `app/db_url.py` — relative sqlite URLs are now
  anchored to the repo root from both `app/config.py` (pydantic validator)
  and `db/env.py`, so backend and alembic cannot drift onto two files again.

- **Model ↔ migration `server_default` drift.** `test_schema_drift.py` caught
  this while being tuned: several columns declare `server_default=...` in the
  Alembic migrations (`0001_initial`, etc.) but the ORM models don't. Columns
  affected: `analytics.views / watch_time_seconds / affiliate_clicks /
  revenue_cents`, `book_sources.score`, `books.status / score`,
  `content_packages.revision_number / is_approved`, `cost_records.estimated_cents`,
  `jobs.status`. Harmless today (SQLite honors the DB-side default), but would
  bite on a metadata-driven `create_all` (fresh test DB, etc.) since rows
  written by SQLAlchemy wouldn't carry the default. Fix: add
  `server_default=...` to the matching `Column(...)` in
  `backend/app/models/*.py` so the two sources of truth agree. The guardrail
  test has `compare_server_default` off for now; flip it on once the model
  side is in sync.

- **0005 migration (series / series_books / format column).** Exists locally
  but not in this repo — originally applied to the empty `db/` SQLite by
  mistake. **Naming collision:** this branch now ships a `0005_render_metadata`
  migration (render stats + narration hash on `content_packages`). Your local
  series migration will need to be renumbered to `0006_series` and have its
  `down_revision` updated from `0004_cost_records` to `0005_render_metadata`
  before it can land.

## Video pipeline — still to wire

- **Render-metadata UI.** Backend now persists `rendered_at`,
  `rendered_duration_seconds`, `rendered_size_bytes`, `rendered_narration_hash`
  on `ContentPackage`, and `GET /books/{id}` returns a computed
  `needs_rerender: bool`. The frontend doesn't consume any of this yet — the
  book page should show a "Needs re-render — narration has changed since the
  last render" banner when `needs_rerender` is true and `rendered_at` is not
  null, plus a subtle "48s · 12MB · rendered 3h ago" line when fresh. Backend
  deps are in place; this is a pure frontend task.

- **Publish stubs.** `services/tiktok.py`, `services/youtube.py`, and
  `services/meta.py` all `raise NotImplementedError` on `upload(...)`. Each is
  externally blocked — TikTok app review, YouTube installed-app OAuth, and a
  public-URL story (tunnel or signed bucket) for Meta Reels + Threads. The
  stubs include the implementation shape inline as comments.

- **Provider stubs.** `services/images.py` and `services/tts.py` only wire
  `wanx` + `openai` today; DALL·E 3, Imagen 3, Replicate FLUX, local SDXL,
  Kokoro, Dashscope CosyVoice, ElevenLabs all `raise NotImplementedError`.
  Low priority while the free/cheap defaults work.
