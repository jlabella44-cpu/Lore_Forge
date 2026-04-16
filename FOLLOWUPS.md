# Followups

Short-lived punch list of known technical debt / later PRs. Delete items as
they land; don't let this turn into a design doc.

## Schema

- **Two-DB divergence (being fixed).** `backend/lore_forge.sqlite` (real data)
  and `db/lore_forge.sqlite` (alembic-only scaffold) were never the same file
  because `DATABASE_URL=sqlite:///./lore_forge.sqlite` is relative to the cwd
  of whoever ran it. Short-term fix on branch
  `claude/stamp-upgrade-real-db-YyS4F`: `cd backend && alembic stamp
  0004_cost_records && alembic upgrade head` (runs locally, not in CI).
  **Root-cause fix (TODO):** resolve `DATABASE_URL` to an absolute path — either
  in `.env.example` or by normalizing in `app/config.py` + `db/env.py`.

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
  mistake. Needs to land as a proper migration once the stamp+upgrade above
  has run against the real backend DB.
