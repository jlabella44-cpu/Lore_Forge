# Parallel Claude handoff — A6: Settings UI + OS keychain

The main Claude session is working on Phase B (generalize to Content
Profiles). You've been launched to handle **A6 (Settings UI for
secrets, backed by the OS keychain)** in parallel. The work splits
cleanly — zero file overlap with Phase B.

## Repo state to start from

```
git fetch origin
git checkout claude/cross-platform-content-tool-fvHxF
git pull
```

Latest commits you should see at the tip:
- A1: anchor runtime paths at OS user-data dir
- A2: static-export the Next.js frontend
- A3+A4: scaffold PyInstaller sidecar + Tauri shell
- A5: ffmpeg-only simple_renderer
- (B1, B2, ... land while you work)

## Your scope (A6)

Implement the mechanism for the packaged desktop app to store provider
API keys in the OS keychain instead of a `.env` file:

1. **Backend — `keyring` integration.** Add a
   `backend/app/services/secrets.py` module that reads/writes secrets
   via `keyring` (Keychain on macOS, DPAPI on Windows, Secret Service
   on Linux). Keys use a flat namespace
   (`loreforge/anthropic_api_key`, etc.). It must work in two modes:
   - **Desktop (`app_base_dir()` non-None)**: `keyring` is the source
     of truth. `config.settings.<key>` reads from keyring at boot and
     caches the value in-process.
   - **Dev (`app_base_dir() is None`)**: fall through to the existing
     `.env` behaviour — no keyring calls, so developers don't have
     to set up keychain access.

   Keys in scope (all currently on `Settings` in `backend/app/config.py`):
   `anthropic_api_key, openai_api_key, dashscope_api_key,
   elevenlabs_api_key, nyt_api_key, firecrawl_api_key, isbndb_api_key,
   youtube_client_id, youtube_client_secret, tiktok_client_key,
   tiktok_client_secret, meta_app_id, meta_app_secret,
   amazon_associate_tag, bookshop_affiliate_id`.

2. **Backend — a new router** at `backend/app/routers/settings.py`:
   - `GET /settings` — returns a sanitised snapshot:
     `{secret_keys: [{name, configured: bool, last_four: str|null}],
      providers: {script, meta, tts, image, renderer}, paths:
      {renders_dir, music_dir, database_url}}`.
     Never return the actual secret values.
   - `PUT /settings/secrets/{name}` — body `{value: str}`. Writes via
     `secrets.set()`, returns the same record shape.
   - `DELETE /settings/secrets/{name}` — removes the keychain entry.
   - `PUT /settings/providers` — body with `{script_provider,
     meta_provider, tts_provider, image_provider, renderer_backend}`,
     validated against the enums. Non-secret toggles live in a small
     `settings.json` in `app_base_dir()`, not keyring. In dev, these
     are session-only.

3. **Frontend — extend `frontend/app/settings/page.tsx`**:
   - Add a "Provider keys" section: one row per secret, showing the
     mask (`••••1234` when configured, "Not set" otherwise) and two
     buttons — "Set" (opens a modal with a password input that
     submits `PUT /settings/secrets/{name}`) and "Clear"
     (`DELETE`). Re-fetches the snapshot on success.
   - Add a "Provider routing" section: four `<select>`s for the
     provider envs, backed by `PUT /settings/providers`.
   - The existing cost / spend UI on that page stays untouched.

4. **Tests** (the main session owns `tests/backend/test_profile*.py`,
   stay out of those):
   - `tests/backend/test_secrets.py` — `keyring` calls are mocked via
     `keyring.set_keyring(<fake>)`. Cover desktop + dev modes.
   - `tests/backend/test_settings_router.py` — FastAPI TestClient
     against the new router, asserts never returns raw values.

## What you must NOT touch

These are under active edit by the main session. Even innocuous
whitespace diffs will merge-conflict:

- `backend/app/models/` (whole directory — Phase B renames models)
- `backend/app/services/llm.py` and `backend/app/services/prompts/`
- `backend/app/services/book_research.py`
- `backend/app/routers/books.py`, `discover.py`, `generate.py`,
  `series.py`
- `backend/app/sources/` (whole directory)
- `db/versions/` — the main session is writing new Alembic migrations
- `frontend/app/dashboard/page.tsx`, `frontend/app/book/page.tsx`,
  `frontend/app/series/*`
- `frontend/components/Sidebar.tsx`, `BookCover.tsx`
- `tests/backend/test_profile*.py` if present
- `CLAUDE.md`, the plan file

If you need an enum or constant that lives in one of those files,
copy the value (don't import from a path that might move).

## Files you own

Create or edit freely:
- `backend/app/services/secrets.py` (new)
- `backend/app/config.py` (add boot-time keyring fetch helper,
  but keep the existing fields and validators — do not rename)
- `backend/app/routers/settings.py` (new)
- `backend/main.py` (register the new router — one line)
- `backend/requirements.txt` (add `keyring==25.*`)
- `frontend/app/settings/page.tsx`
- `frontend/components/` — new UI primitives for the secret mask /
  modal if you need them. Name them distinctly so they don't clash
  with existing ones.
- `tests/backend/test_secrets.py` (new)
- `tests/backend/test_settings_router.py` (new)

## Verification before you commit

```bash
cd tests && ../backend/.venv/bin/python -m pytest backend/ -v
cd ../frontend && npm run build
```

Both must be green. The full backend suite is currently 237/237 after
A5; your PR should keep that count or add to it.

## Branch + commit

Stay on `claude/cross-platform-content-tool-fvHxF`. Rebase on top of
the main session's commits when you push:

```bash
git fetch origin
git rebase origin/claude/cross-platform-content-tool-fvHxF
# resolve if anything clashes (shouldn't, given the split above)
git push
```

Commits: one per concern (`secrets service`, `settings router`,
`settings UI`, `tests`) so the main session can cherry-pick if
something needs to be reverted mid-flight.

## Starting prompt to paste

```
Read docs/parallel-claude-handoff-a6.md and implement A6 exactly as
scoped there. The main Claude session is working Phase B in parallel;
stay out of the files that doc lists as off-limits. Commit each
concern separately on the existing feature branch and push when the
backend suite is 237+/237+ green and `npm run build` succeeds.
```
