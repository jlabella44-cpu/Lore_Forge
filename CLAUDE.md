# Lore Forge — Claude Code Instructions

## Project Structure
- /frontend   → Next.js 14 app (Frontend Agent owns this)
- /backend    → FastAPI app + APScheduler jobs (Backend Agent owns this)
- /db         → Alembic migrations (DB Agent owns this)
- /tests      → Pytest + Playwright (Test Agent owns this)

## Agent Rules
- Frontend Agent: ONLY touches /frontend. Never edits backend files.
- Backend Agent: ONLY touches /backend. Never edits /frontend.
- DB Agent: ONLY touches /db. Coordinate with Backend on schema changes.
- Test Agent: ONLY touches /tests. Reads all other dirs, writes none.

## Posture
Solo + local-first. Shorts-only (TikTok, YouTube Shorts, Instagram Reels, Threads).
No YouTube long-form. Every cost center has a free/cheap default provider.

## Stack
- Frontend: Next.js 14, Tailwind CSS, shadcn/ui
- Backend: FastAPI, Python 3.11, SQLAlchemy
- Database: SQLite (dev) → PostgreSQL (prod), Alembic migrations
- Orchestration: APScheduler (in-process)
- Video assembly (Phase 2): Remotion

## Provider matrix (all pluggable via env)
| Role | Default | Swaps |
|---|---|---|
| Script + image prompts | Claude Opus 4.6 | OpenAI · Qwen |
| Classify + titles/hashtags | Qwen Plus (Dashscope) | Claude · OpenAI |
| TTS narration | OpenAI TTS | Kokoro (local, free) · Dashscope CosyVoice · ElevenLabs |
| Image generation | Wanx (Dashscope) | DALL-E 3 · Imagen 3 · Replicate FLUX · Local SDXL · Midjourney (manual) |

Env vars: `SCRIPT_PROVIDER`, `META_PROVIDER`, `TTS_PROVIDER`, `IMAGE_PROVIDER`.

## Publish targets (Phase 2)
TikTok · YouTube Shorts · Instagram Reels · Threads. Manual Approve click
required in the dashboard before any upload — no auto-fire.

## Key Commands
- Frontend: cd frontend && npm run dev
- Backend: cd backend && uvicorn main:app --reload
- DB migrations: cd db && alembic upgrade head
