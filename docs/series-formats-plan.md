# Lore Forge — Series, Formats & Publishing Plan

> Implementation plan written for a fresh session. Self-contained: read this file first, then jump to the file references.

---

## 0. Read this first (orientation)

**What Lore Forge is**: A book → marketing-video factory. Given a book, it generates a script, scene image prompts, narration, captions, and renders a final MP4 via Remotion. Per-platform titles + hashtags are produced for TikTok / YouTube Shorts / Instagram Reels / Threads. Cost is tracked per-call with a daily budget cap.

**What this plan adds**: Series grouping ("Part 3 of 5"), six video formats (currently only one short-hook format exists), a publish pipeline with scheduled drops, analytics ingestion with a hook-A/B feedback loop, and revenue plumbing.

**Tech stack (fixed — do not swap)**:
- Backend: FastAPI on SQLite (Alembic for migrations), APScheduler for cron
- LLMs: Claude Opus 4.6 (script + prompts), Qwen Plus via Dashscope (cheap meta), routable via env
- Image gen: Wanx via Dashscope (`dashscope.ImageSynthesis`)
- TTS: OpenAI tts-1 (ElevenLabs/Kokoro/CosyVoice are pluggable stubs)
- Transcription: OpenAI Whisper (word-level captions)
- Video render: Remotion (`npx remotion render`), composition `LoreForge.tsx`
- Frontend: Next.js 14 App Router + Tailwind + shadcn/ui

**The marketing plan (`Marketing Strategy, Series Formats & Production Schedule`) is the *what*, not the *how*.** It assumes manual CapCut + Midjourney copy/paste + 90 min/video. Reality: pipeline is fully automated, ~60s end-to-end once triggered. Use the marketing plan for series naming, format intent, cadence, and growth tactics — ignore its tooling assumptions.

---

## 1. Codebase audit (current state, dense)

### Repo layout
```
backend/    FastAPI, services, routers, models, scheduler, cost tracking
frontend/   Next.js 14 dashboard
remotion/   Remotion compositions (LoreForge.tsx + scenes/theme/types)
db/         Alembic migrations (4 versions)
scripts/    setup_env.sh (syncs API keys from sibling projects)
tests/      Pytest (10 backend test files)
```

### Data model (`backend/app/models/`)

| Model | Important columns | Notes |
|---|---|---|
| **Book** | id, title, author, isbn, asin, cover_url, description, genre, genre_confidence, genre_override, status (discovered→generating→review→scheduled→published), score, discovered_at | 1→many ContentPackage |
| **ContentPackage** | id, book_id (FK), revision_number, script (md), narration (prose), hook_alternatives (JSON list), chosen_hook_index, visual_prompts (JSON), section_word_counts (JSON), captions (JSON word-level), titles (JSON per-platform), hashtags (JSON per-platform), affiliate_amazon, affiliate_bookshop, regenerate_note, is_approved, created_at | One row per revision |
| **CostRecord** | id, created_at (idx), call_name, provider, model, input_tokens, output_tokens, cache_read/write_tokens, units, estimated_cents, package_id (nullable FK) | Discovery calls have null package_id |
| **Job** | id, kind ("generate"\|"render"), target_id (idx), status, message (live progress), result (JSON), error, created_at, started_at, finished_at | Threading-based async |
| **Video** | id, book_id, package_id, platform ("tiktok"\|"yt_shorts"\|"ig_reels"\|"threads"), file_path, external_id, published_at | Stub — no upload code |
| **Analytics** | id, video_id, date, views, watch_time_seconds, affiliate_clicks, revenue_cents | Stub — no ingest code |
| **BookSource** | id, book_id, source ("nyt"\|"goodreads"\|"booktok"\|"amazon"\|"reddit"), score, discovered_at | Only NYT is wired |

### Pipeline today (`backend/app/routers/generate.py::_generate_core_with_progress`)

1. **Hooks** — Claude → 3 hook variants + chosen index (`hook_alternatives`, `chosen_hook_index`)
2. **Script + narration** — Claude → 5-section markdown (HOOK/WORLD/EMOTIONAL/SOCIAL PROOF/CTA) + narration prose + section_word_counts
3. **Scene prompts** — Claude → 5 image prompts (9:16, no faces)
4. **Platform meta** — Qwen Plus → titles + hashtags per platform

Render (`backend/app/services/renderer.py::render_package`):
1. Tone derived from genre (fantasy/thriller→dark, scifi→hype, romance/hist_fic→cozy)
2. OpenAI TTS → narration MP3
3. Whisper → word-level captions
4. Wanx → 5 PNG images (720×1280)
5. Audio probe → per-scene timing from section_word_counts
6. Write `props.json` → `npx remotion render LoreForge --props props.json` → `renders/{package_id}/out.mp4`

### Frontend endpoints used (`frontend/lib/api.ts`)
`GET /books`, `GET /books/{id}`, `PATCH /books/{id}`, `POST /discover/run`, `POST /books/{id}/generate?async=true`, `POST /packages/{id}/render?async=true`, `POST /packages/{id}/approve`, `POST /publish/{package_id}/{platform}`, `GET /analytics/cost`, `GET /jobs/{id}` (polled at 1.2s).

### What's stubbed
- `services/youtube.py`, `services/tiktok.py`, `services/meta.py` — all `raise NotImplementedError`
- TTS alternatives (ElevenLabs/Kokoro/CosyVoice) — stubs
- Image gen alternatives (DALL·E 3, Imagen, Replicate FLUX, local SDXL) — stubs
- Analytics ingestion — model exists, no fetcher
- Discovery sources beyond NYT (Goodreads/Reddit/BookTok/Amazon) — env keys present, code missing
- Thumbnails — no generation step

### Known issues to keep in mind
- **SQLite "database is locked"** in `backend/app/services/cost.py::attach_pending_to` under write contention. Currently swallowed — leaves cost records orphaned from packages. Fix candidates: (a) `PRAGMA journal_mode=WAL` + busy_timeout, (b) retry wrapper, (c) move cost attach into the same transaction as package commit so the timestamp ordering bug also goes away (currently the package is committed *after* its records, so any backfill must look forward in time, see `services/cost.py`).
- **uvicorn `--reload` doesn't cleanly restart on Windows** when APScheduler's BackgroundScheduler is alive. Workaround: develop without `--reload` (`./.venv/Scripts/python.exe -m uvicorn main:app`).
- **APScheduler import** is required (`pip install apscheduler` already done in `.venv`; ensure it's in `requirements.txt`).

---

## 2. Phase plan (5 phases, ship Phase 1 first)

### Phase 1 — Series + VideoFormat foundation **(first PR)**

**Goal**: One new format (`LIST`) shipping end-to-end alongside the existing short-hook flow, using Series as the grouping primitive.

**Models** (`backend/app/models/`)
- New `Series` model:
  ```
  id, slug (unique), title, description, format (FK to VideoFormat),
  series_type ("multipart_book" | "author_ranking" | "themed_list" |
               "universe_explainer" | "recap" | "monthly_report"),
  source_book_id (nullable FK — for multipart_book series),
  source_author (nullable string — for author_ranking),
  total_parts (nullable int), status ("active" | "complete" | "paused"),
  created_at
  ```
- New `SeriesBook` join (for series that span multiple books):
  ```
  series_id, book_id, position (int)
  ```
- Add to `ContentPackage`: `series_id` (nullable FK), `part_number` (nullable int), `format` (string, default `"short_hook"`)

**Enum** (`backend/app/models/format.py` — new file)
```python
class VideoFormat(str, Enum):
    SHORT_HOOK     = "short_hook"      # existing 60-90s teaser
    LIST           = "list"            # "Top N books for X"
    AUTHOR_RANKING = "author_ranking"  # "Every Sanderson Book Ranked"
    SERIES_EPISODE = "series_episode"  # "Part 2 of 5"
    DEEP_DIVE      = "deep_dive"       # 8-15min lore explainer
    RECAP          = "recap"           # "Read This Before Book 2"
    MONTHLY_REPORT = "monthly_report"  # "BookTok in April"
```

**Migration** — new Alembic revision adding the above; backfill existing `ContentPackage.format = "short_hook"`.

**Prompt templates** (`backend/app/services/prompts/`)
- Refactor existing prompts into a `format_registry`: `dict[VideoFormat, FormatPromptBundle]` where each bundle has `hooks_prompt`, `script_prompt`, `scene_prompts_prompt`, `meta_prompt`, plus per-format constants (target_duration_sec, scene_count, tone defaults).
- For LIST format: input is a list of book_ids; script structure is intro → N book mini-pitches × 20-30s each → CTA. Scene prompts are one per book (cover-style or thematic).

**Routes** (`backend/app/routers/series.py` — new)
- `POST /series` — create a Series row
- `POST /series/{id}/books` — attach books (for list/ranking)
- `POST /series/{id}/generate` — run pipeline producing N ContentPackages (or 1 list-style package, depending on series_type) with proper `series_id`, `part_number`
- `GET /series` / `GET /series/{id}` — list/detail

**Pipeline change** (`backend/app/routers/generate.py`)
- Read `format` off the package (or from request param), look up the format bundle, dispatch to the right prompt set. Keep backward compat: missing format = `SHORT_HOOK`.

**Renderer change** (`backend/app/services/renderer.py`)
- Compute composition name from `package.format`. For Phase 1: `SHORT_HOOK` → `LoreForge`, `LIST` → `LoreForgeList` (new).

**Remotion** (`remotion/`)
- New `LoreForgeList.tsx` composition. Same audio + caption pipeline; scenes are per-book (image + book title + author overlay) instead of per-section.
- Update `remotion/Root.tsx` (or wherever compositions are registered) to expose the new composition.

**Tests**
- `tests/backend/test_series.py` — create series, attach books, dispatch generate.
- Mock LLM/TTS/image as existing tests do.

**Frontend (minimum)**
- `/series` page: list series with status badges
- `/series/[id]`: show packages with "Part N of M" badges, actions to render/approve

**Acceptance for Phase 1**: Create a "Top 10 Fantasy for GoT Fans" Series, add 10 books, hit `POST /series/{id}/generate`, get one rendered MP4 with 10 book mini-scenes.

---

### Phase 2 — Long-form Remotion compositions

- `LoreForgeDeepDive.tsx` — 8–15 min, slower pacing, more scenes per section, lore-heavy
- `LoreForgeAuthorRanking.tsx` — author intro + ranked book scenes
- `LoreForgeRecap.tsx` — sequential book recap (short, hook-style)
- `LoreForgeMonthlyReport.tsx` — list-like with trend annotations
- Thumbnail: render a still frame at t=2s into `renders/{package_id}/thumb.png`. Add `package.thumbnail_path`.
- Renderer dispatches composition by `format` (registry pattern).

---

### Phase 3 — Publishing

**Implement upload services** (currently `NotImplementedError`):
- `services/youtube.py`: OAuth refresh + Data API v3 resumable upload. Set `categoryId`, `tags` (from `package.hashtags["yt_shorts"]`), `title` (from `package.titles["yt_shorts"]`), description (template with affiliate links).
- `services/tiktok.py`: Content Posting API (Direct Post). Caption from `titles["tiktok"]` + hashtags.
- `services/meta.py`: IG Reels via Graph API (container → publish). Threads via Threads API.

**ScheduledPublish model**
```
id, package_id, platform, publish_at (UTC), status ("pending"|"running"|"published"|"failed"),
external_id, attempts, last_error, created_at, published_at
```

**Cron executor** — APScheduler IntervalTrigger every minute: pick `status="pending" AND publish_at<=now()`, mark running, call platform service, update status. Already-bootstrapped scheduler in `app/scheduler.py::register_jobs`.

**Routes**
- `POST /publish/schedule` — body: `{package_id, platform, publish_at}`
- `GET /publish/calendar?from=&to=` — calendar view

**Frontend**
- `/calendar` — week view of scheduled drops, drag to reschedule

---

### Phase 4 — Analytics ingestion + hook A/B feedback

**Daily ingest cron** (`app/services/analytics_ingest.py`)
- For each `Video` with `external_id` and `published_at < today`:
  - YouTube: Analytics API v2 (`youtubeAnalytics.reports.query`) → views, estimatedMinutesWatched
  - TikTok: Research API → video_views, total_time_watched
  - IG: Graph API insights → reach, plays
- Upsert into `Analytics(video_id, date, ...)`

**Hook A/B loop**
- After 7 days of data: if a hook variant underperforms peer median by >40%, mark the package `regenerate_note="hook_underperformed"` and auto-render with `chosen_hook_index = next variant`. Re-publish to the platforms where it lost.

**Scoring feedback**
- Re-weight `Book.score` using actual video performance (avg views per book → score multiplier), not just discovery source heuristics.

---

### Phase 5 — Growth & revenue plumbing

- **Affiliate redirect endpoint** `/go/{asin}/{platform}` → 302 to Amazon/Bookshop with UTM params, increments `Analytics.affiliate_clicks`.
- **Email capture** — landing page `/list` with weekly trending list, integrate Resend (or Mailchimp).
- **Discovery expansion** — wire Goodreads scraper, Reddit (r/Fantasy, r/printSF), BookTok trends. Env keys already exist (`REDDIT_USER_AGENT`, `FIRECRAWL_API_KEY`).
- **Bulk ingest** — `POST /books/bulk` accepting CSV of ISBNs.
- **Sponsored content type** — extend `Video` with `sponsor_id`, `sponsor_disclosure`, separate revenue line in Analytics.

---

## 3. Phase 1 first-PR checklist

```
[ ] alembic revision: add series, series_book, content_packages.{series_id,part_number,format}
[ ] backend/app/models/format.py: VideoFormat enum
[ ] backend/app/models/series.py: Series, SeriesBook
[ ] backend/app/models/__init__.py: re-export
[ ] backend/app/services/prompts/__init__.py: format_registry
[ ] backend/app/services/prompts/short_hook.py: extract existing prompts
[ ] backend/app/services/prompts/list_format.py: new
[ ] backend/app/routers/generate.py: dispatch by format
[ ] backend/app/routers/series.py: new endpoints
[ ] backend/app/services/renderer.py: composition by format
[ ] remotion/LoreForgeList.tsx: new composition
[ ] remotion/Root.tsx: register
[ ] tests/backend/test_series.py
[ ] tests/backend/test_format_dispatch.py
[ ] frontend/app/series/page.tsx
[ ] frontend/app/series/[id]/page.tsx
[ ] frontend/lib/api.ts: series endpoints
[ ] docs/series-formats-plan.md (this file): mark Phase 1 done
```

---

## 4. How to resume in a fresh session

1. **`cd C:\Users\Jeff\dev\Lore_Forge`**
2. **`git pull`**
3. **Read** `docs/series-formats-plan.md` (this file) and `CLAUDE.md` (root).
4. **Skim** `backend/app/models/__init__.py`, `backend/app/routers/generate.py`, `backend/app/services/renderer.py`, `remotion/LoreForge.tsx`.
5. **Start backend**: from `backend/`, run `./.venv/Scripts/python.exe -m uvicorn main:app` (no `--reload` on Windows — APScheduler blocks shutdown).
6. **Start frontend**: from `frontend/`, run `npm run dev`.
7. **Verify health**: `GET http://127.0.0.1:8000/analytics/cost` returns JSON.
8. **Pick the next unchecked box** from §3 and go.

### Useful invariants to preserve
- Every LLM call goes through `app/services/llm.py` so cost tracking attaches.
- Every long-running operation goes through `Job` (threading worker, `set_progress` callback) so the UI can poll.
- Cost records that aren't tied to a package (discovery, classification) should keep `package_id=NULL`. Don't backfill those.
- Render output path is canonical: `renders/{package_id}/out.mp4`. Don't change without updating the publish services.
- Frontend `pollJob` polls every 1.2s — keep `set_progress` calls cheap.

### Things NOT to do in Phase 1
- Do NOT implement upload services (Phase 3).
- Do NOT add analytics ingestion (Phase 4).
- Do NOT migrate off SQLite (still fine at this scale; revisit in Phase 4 if WAL + busy_timeout don't resolve lock contention under publish-cron load).
- Do NOT add a thumbnail step (Phase 2).
- Do NOT touch `services/cost.py::attach_pending_to` here; the cost-orphan bug is real but unrelated to this PR. File an issue, fix in a separate PR with WAL mode.
