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

## Stack
- Frontend: Next.js 14, Tailwind CSS, shadcn/ui
- Backend: FastAPI, Python 3.11, SQLAlchemy
- Database: SQLite (dev) → PostgreSQL (prod), Alembic migrations
- Orchestration: APScheduler (in-process)
- AI: Anthropic Claude API (claude-sonnet-4-20250514)
- Voice: ElevenLabs API (Phase 2)
- Publishing: YouTube Data API v3, TikTok Content Posting API, Meta Graph (IG Reels + Threads) (Phase 2)

## Key Commands
- Frontend: cd frontend && npm run dev
- Backend: cd backend && uvicorn main:app --reload
- DB migrations: cd db && alembic upgrade head
