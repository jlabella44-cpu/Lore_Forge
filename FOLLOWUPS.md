# Followups

Short-lived punch list of known technical debt / later PRs. Delete items as
they land; don't let this turn into a design doc.

Session history (what just shipped) lives in `docs/SESSION_SUMMARY.md`.

## Local action before Phase 1 resumes

- **Stamp + upgrade the real backend DB.** Nothing in the merged PR touched
  on-disk data on your machine. Run once:
  ```bash
  cd backend
  alembic stamp 0004_cost_records
  alembic upgrade head
  ```
  That declares the existing schema as `0004_cost_records` (what
  `Base.metadata.create_all` organically built) and then applies
  `0005_render_metadata` for the new `rendered_*` columns. Without this,
  reads against `content_packages` will 500.

## Schema

- **0005 migration collision (series / series_books / format column).**
  Your local uncommitted series migration is also named `0005`. On the
  repo, `0005_render_metadata` has taken that slot. Before landing your
  series work: rename the file to `0006_series.py`, change `revision` to
  `"0006_series"`, change `down_revision` to `"0005_render_metadata"`.

## Video pipeline — still to wire

- **Frontend `needs_rerender` banner.** Backend already persists
  `rendered_at / rendered_duration_seconds / rendered_size_bytes` and
  `GET /books/{id}` returns `needs_rerender: bool`. The book page should
  show a "Needs re-render — narration has changed since the last render"
  banner when `needs_rerender` is true and `rendered_at` is non-null, plus
  a subtle "48s · 12MB · rendered 3h ago" line when fresh. Pure frontend
  task — I couldn't run the UI in the agent env so it was left off.

- **Publish stubs.** `services/tiktok.py`, `services/youtube.py`, and
  `services/meta.py` all `raise NotImplementedError` on `upload(...)`. Each
  is externally blocked — TikTok app review for the `video.publish` scope,
  YouTube installed-app OAuth, and a public-URL story (tunnel or signed
  bucket) for Meta Reels + Threads. The stubs include the implementation
  shape inline as comments so pick-up is low-friction once the external
  gate clears.

- **Provider stubs.** `services/images.py` and `services/tts.py` only wire
  `wanx` + `openai` today; DALL·E 3, Imagen 3, Replicate FLUX, local SDXL,
  Kokoro, Dashscope CosyVoice, ElevenLabs all `raise NotImplementedError`.
  Low priority while the free/cheap defaults work.

## Deployment

- **Remote hosting plan** is parked on branch `claude/deployment-notes`
  (docs/CHEAP_HOSTING.md) — one ~$5/mo Hetzner VPS covers the whole stack.
  Pick up when ready to take this off local-only.
