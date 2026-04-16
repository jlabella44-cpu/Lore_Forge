# Cheap Remote Hosting Plan

Solo + local-first posture today. This doc captures the cheapest path to
serving Lore Forge remotely without giving up things that currently work
(APScheduler in-process, Remotion's filesystem render, public URLs for Meta).

## Constraints that shape the answer

Three non-negotiables from the current stack:

1. **APScheduler is in-process.** Weekly discovery cron runs inside the
   uvicorn process (`app/scheduler.py`). That rules out stateless serverless
   — Vercel Functions / AWS Lambda / Cloud Run cold-starts drop the
   scheduler. We need a **single always-on process** (or rip APScheduler out
   and use an external cron).
2. **Remotion wants Chromium + ~2 GB RAM + a writable filesystem.** Each
   render writes `narration.mp3`, `scene_NN_*.png`, `props.json`, and
   `out.mp4` to `renders_dir`. Fine on a VPS or a Fly Machine; bad fit for
   function-shaped runtimes.
3. **Meta Reels + Threads fetch by public URL.** `services/publish.py`'s
   `_public_url_for` still `raise`s — Meta won't accept local file uploads.
   Whatever hosts `renders/` needs a public URL, either the VPS's own
   `/renders` route behind a domain, or a public object bucket (R2).

## Recommended starter stack — ~$5/mo all-in

| Piece | Service | Cost | Notes |
|---|---|---|---|
| Box | **Hetzner CX22** (2 vCPU / 4 GB / 40 GB) | ~$4.60/mo | Ashburn or Falkenstein. Bump to CX32 (~$6/mo) if Remotion feels tight on 4 GB. |
| TLS + reverse proxy | **Caddy** | free | One-line `Caddyfile`, automatic Let's Encrypt certs. |
| FastAPI | `uvicorn` under `systemd` | — | `/api/*` reverse-proxied through Caddy. |
| Next.js | `next start` under `systemd` (or static-export → **Cloudflare Pages** free) | — | Vercel Hobby also works and gives you previews for free. |
| DB | **SQLite on disk** | — | WAL + `busy_timeout=30000` already wired in `app/db.py`. Only move to Postgres when concurrent-writer pain is real. |
| SQLite backup | **Litestream → Cloudflare R2** | pennies/mo | Streams the WAL; near-zero RPO. |
| Rendered mp4s | local `/var/lib/lore-forge/renders` served by Caddy at `https://api.yourdomain.com/renders/*` | — | Solves `_public_url_for` for Meta Reels for free. |
| LLM / image / TTS | Claude / OpenAI / Dashscope (existing) | **dominant cost** | Infra bill will be ~5% of the LLM bill. |
| CI | GitHub Actions (already set up) | free | Add a deploy step: `ssh host 'cd /opt/lore-forge && git pull && systemctl reload lore-forge-api'`. |

## When to split it up

- **Frontend → Vercel free** — if you want preview deploys and global CDN
  for free. Then the VPS only runs FastAPI + Remotion + SQLite. Adds a CORS
  origin to whitelist, nothing else.
- **mp4s → R2** — free 10 GB, zero egress. Only worth the extra complexity
  past ~1 GB of retained renders or when you want lifecycle rules
  (e.g. delete unpublished renders > 30 days old).
- **DB → Neon / Supabase free tier** — only if you outgrow single-writer
  SQLite. Unlikely on shorts-only solo posture.

## What to skip

- **Render.com free web service** — spins down after 15 min idle, kills
  APScheduler.
- **Lambda / Cloud Run / Vercel Functions** — stateless + cold-start
  incompatible with the in-process scheduler, and Remotion is a poor fit
  for function-shaped runtimes.
- **Managed Postgres from day one** — overkill for single-writer workloads,
  adds $5–20/mo for no user-visible benefit yet.

## Sketch: what provisioning looks like

Not prescriptive — just so the shape is clear.

```
/opt/lore-forge/            # git clone of this repo
/var/lib/lore-forge/
  lore_forge.sqlite          # the real DB (one file, absolute path — solves the divergence bug in FOLLOWUPS.md)
  renders/                   # per-package working dirs + out.mp4s
  music/                     # tone-keyed bgm library

/etc/systemd/system/
  lore-forge-api.service     # ExecStart=/opt/lore-forge/backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
  lore-forge-web.service     # ExecStart=/opt/lore-forge/frontend/node_modules/.bin/next start -p 3000

/etc/caddy/Caddyfile
  api.yourdomain.com {
      reverse_proxy 127.0.0.1:8000
  }
  yourdomain.com {
      reverse_proxy 127.0.0.1:3000
  }
```

Remotion's `npx remotion render` is invoked as a subprocess of
`lore-forge-api.service` (see `services/renderer.py`), so no separate unit —
just install Node + Chromium once on the box.

## Dependencies before going remote

A few loose ends from `FOLLOWUPS.md` matter more in production than locally:

- **Absolute `DATABASE_URL`** — the `sqlite:///./lore_forge.sqlite` relative
  path is how `backend/` and `db/` ended up with two different databases
  locally. In production, a relative path resolves against whoever's cwd
  starts the process, which is brittle. Set it to e.g.
  `sqlite:////var/lib/lore-forge/lore_forge.sqlite` in the service env.
- **`COST_DAILY_BUDGET_CENTS`** — already wired as a guardrail; pick a
  production number and set it in the service env.
- **`DISCOVERY_CRON_ENABLED=true`** — off in `.env.example` so dev
  `uvicorn --reload` doesn't fire real API calls; flip on in production.

## Rough monthly cost model (solo usage, ~1 short/day)

| Line | Cost |
|---|---|
| Hetzner CX22 | $5 |
| Domain | $12/yr ≈ $1/mo |
| R2 backup (SQLite + old renders, ~2 GB) | ~$0.03 |
| Claude Opus 4.6 (1 script + hooks/day, cached system prompt) | $3–6 |
| OpenAI TTS (~90s/day at tts-1) | $0.40 |
| Dashscope Wanx (5 images/day at ~$0.05/img) | $7–8 |
| NYT API | free tier |
| **Total** | **~$16–20/mo** |

LLM + image is ~90% of that. The box itself is a rounding error.
