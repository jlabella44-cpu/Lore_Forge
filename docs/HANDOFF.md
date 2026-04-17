# Lore Forge — Session Handoff (2026-04-17)

## What was done this session

### Phase 1: Series & Format System (committed, PR #3 open)
- **Models**: Series, SeriesBook, VideoFormat enum + migration 0006
- **Prompt registry**: FormatPromptBundle with SHORT_HOOK and LIST bundles
- **Pipeline**: format-aware generate dispatch (_pipeline_short_hook, _pipeline_list)
- **Series router**: 5 endpoints (CRUD + generate) wired in main.py
- **Renderer**: composition dispatch (LoreForge vs LoreForgeList)
- **Remotion**: LoreForgeList.tsx with book title badges
- **Tests**: 20 new (series CRUD, list gen, format dispatch), 139 total passing
- **Frontend**: Sidebar nav + polished series list/detail pages

### Runtime fixes (committed)
- DALL-E 3 image provider wired (was stubbed)
- Whisper dict/attribute compat fix
- Remotion http:// asset URLs (was file:/// which broke)
- Windows shell=True for npx subprocess
- Per-stage render progress callbacks
- Migration renumbered 0005 → 0006 (ultraplan took 0005 slot)

### Sync & TTS fixes (UNCOMMITTED — 6 modified files)
1. **Caption sync** — Audio wrapped in `<Sequence from={cardFrames}>` so narration starts after intro card, matching caption overlay timing
2. **Scene sync** — `_snap_to_frames()` helper snaps durations to 1/30s boundaries; last scene absorbs rounding remainder via `totalFrames` prop
3. **Expressive TTS** — Upgraded to `tts-1-hd`, per-tone voice+speed (`dark`→onyx@0.9x, `hype`→nova@1.1x, `cozy`→shimmer@0.95x), configurable via `TTS_MODEL` env
4. **Section breaks** — `[BREAK]` markers → triple ellipsis for longer TTS pauses between sections

## Uncommitted files
```
M backend/app/config.py          — added tts_model setting
M backend/app/services/renderer.py — _snap_to_frames + frame-snapped durations
M backend/app/services/tts.py    — tts-1-hd, speed param, [BREAK] support
M remotion/src/LoreForge.tsx     — Audio in Sequence, totalFrames to SceneSequence
M remotion/src/LoreForgeList.tsx  — same Audio fix + totalFrames
M remotion/src/scenes/SceneSequence.tsx — accepts totalFrames, fills last scene
```

## To resume

### 1. Start servers
```bash
cd C:\Users\Jeff\dev\Lore_Forge\backend
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000

cd C:\Users\Jeff\dev\Lore_Forge\frontend
npm run dev
```

### 2. Commit the uncommitted sync/TTS fixes
```bash
cd C:\Users\Jeff\dev\Lore_Forge
git add backend/app/config.py backend/app/services/renderer.py backend/app/services/tts.py remotion/src/LoreForge.tsx remotion/src/LoreForgeList.tsx remotion/src/scenes/SceneSequence.tsx
git commit -m "Fix caption/scene sync, upgrade TTS to tts-1-hd with per-tone speed"
git push origin claude/setup-lore-forge-vxC5l
```

### 3. Test the full pipeline
- Pick a book from the dashboard
- Generate (creates new content with [BREAK] markers in prompts)
- Approve
- Render (uses tts-1-hd + DALL-E 3 + frame-snapped durations)
- Verify: captions sync with audio, scenes match sections, narration sounds expressive

### 4. Stamp the real backend DB (if not done)
The backend DB needs migration 0006 applied:
```bash
cd C:\Users\Jeff\dev\Lore_Forge
DATABASE_URL="sqlite:///C:/Users/Jeff/dev/Lore_Forge/backend/lore_forge.sqlite" backend/.venv/Scripts/alembic.exe -c db/alembic.ini upgrade head
```

## Open items
- **PR #3** — open at https://github.com/jlabella44-cpu/Lore_Forge/pull/3
- **3 test failures** — Windows path format (test_db_url, test_paths) from ultraplan's Linux-only assertions, not our code
- **Multi-image scenes** (Fix 4 from plan) — not yet implemented. Would add 1-3 images per script section based on word count
- **Google Drive upload** — authenticated but MCP connector didn't stick. Retry `/mcp` → Google Drive
- **IMAGE_PROVIDER** — currently set to `dalle` in .env (Dashscope key expired). Switch back to `wanx` when key is renewed

## Key env vars (.env)
```
IMAGE_PROVIDER=dalle          # was wanx, switched due to expired Dashscope key
TTS_MODEL=tts-1-hd            # new — defaults to tts-1-hd in config.py
DATABASE_URL=sqlite:///./lore_forge.sqlite  # relative — resolves per CWD
```

## Branch state
- Branch: `claude/setup-lore-forge-vxC5l`
- Base: `main` (includes ultraplan PRs #1 and #2)
- 8 commits ahead of main + 6 uncommitted files
