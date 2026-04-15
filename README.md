# Lore Forge

Automated book-content pipeline. Discover trending books → generate spoiler-free scripts, image prompts, narration, and per-platform metadata via Claude → review in a dashboard → assemble + publish short/long-form videos to YouTube, TikTok, YouTube Shorts, Instagram Reels, and Threads.

**Posture:** solo + local-first. SQLite for dev, Postgres-ready for later.

## Layout

```
frontend/   Next.js 14 (App Router, Tailwind, shadcn/ui)
backend/    FastAPI + SQLAlchemy + APScheduler
db/         Alembic migrations
tests/      pytest + Playwright
```

See [CLAUDE.md](./CLAUDE.md) for agent-ownership rules.

## Bootstrap

```bash
# 1. Copy envs
cp .env.example .env
cp frontend/.env.local.example frontend/.env.local

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload           # http://localhost:8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                          # http://localhost:3000

# 4. Migrations (new terminal)
cd db
alembic upgrade head
```

## Roadmap

- **Phase 1** — Content engine for one book end-to-end (NYT source → Claude package → review/approve in UI).
- **Phase 2** — Remotion video assembly → expand discovery sources → ElevenLabs narration → auto-publish (gated on manual Approve).
- **Phase 3** — Analytics dashboard, A/B title testing, prompt-feedback loop.
