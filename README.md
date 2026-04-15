# Lore Forge

Automated short-form book-content pipeline. Discover trending books → generate a
90-sec script, image prompts, narration, and per-platform metadata → review in
a dashboard → assemble + publish shorts to TikTok, YouTube Shorts, Instagram
Reels, and Threads.

**Posture:** solo + local-first, shorts-only. SQLite for dev, Postgres-ready.
Every expensive step is behind a pluggable provider with a free/cheap default.

> **TODO (when back at your machine):** run `./scripts/setup_env.sh` to pull
> the shared Anthropic / OpenAI / Dashscope keys from `~/listingjet/.env`
> (or pass a different path as `$1`). This avoids maintaining two copies of
> the same keys. The script is idempotent and only touches those three
> variables — NYT / Firecrawl / affiliate tags stay whatever you set.

## Layout

```
frontend/   Next.js 14 (App Router, Tailwind, shadcn/ui)
backend/    FastAPI + SQLAlchemy + APScheduler
remotion/   Remotion video assembly (Phase 2+)
db/         Alembic migrations
tests/      pytest + Playwright
```

See [CLAUDE.md](./CLAUDE.md) for agent-ownership rules and the provider matrix.

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

# 5. (Optional) Seed sample data so the UI demos without API keys
cd ../backend
python -m app.seed
```

`app.seed` is idempotent; re-running it won't duplicate rows. Pass
`--wipe` to start fresh.

## Provider defaults

Cheapest working path using existing keys (Anthropic + OpenAI + Dashscope/Qwen):

- **Script generation** — Claude Sonnet 4 (quality-sensitive)
- **Genre / titles / hashtags** — Qwen Plus via Dashscope (cheap + formulaic)
- **TTS narration** — OpenAI TTS (~$0.014/short)
- **Image generation** — Alibaba Wanx via Dashscope (free quota on new accounts)

All four are swappable via env vars — see [.env.example](./.env.example).

**Expected spend for 50 shorts over 90 days:** single-digit dollars, assuming
you stay on the default providers.

## Roadmap

- **Phase 1** — Content engine end-to-end for one book. NYT source → Claude
  package → dashboard review → approve. No uploads yet.
- **Phase 2** — Remotion video assembly (per-tone template + free music
  library) → expand discovery sources → TTS automation → publish to all four
  short-form targets, still gated on manual Approve.
- **Phase 3** — Analytics dashboard, A/B title testing, feedback loop from
  performance into Claude prompts.
