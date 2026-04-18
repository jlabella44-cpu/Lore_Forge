from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import APP_BASE_DIR, settings
from app.db import init_db
from app.migrations import run_migrations_to_head
from app.observability import configure_logging, get_logger
from app.routers import analytics, discover, generate, items, jobs, publish, series
from app.scheduler import register_jobs, scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    log = get_logger("startup")
    log.info("Lore Forge API booting")
    # In the packaged desktop build there's no terminal to run alembic
    # from, so the app must bring its own DB up to head on every boot.
    # In dev (APP_BASE_DIR is None), developers run alembic manually so
    # they stay in control of when migrations fire.
    if APP_BASE_DIR is not None:
        log.info("Running alembic upgrade head (desktop mode)")
        run_migrations_to_head()
    init_db()
    register_jobs()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        log.info("Lore Forge API stopped")


app = FastAPI(title="Lore Forge API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(discover.router, prefix="/discover", tags=["discover"])
app.include_router(items.router, prefix="/books", tags=["items"])
app.include_router(generate.router, tags=["generate"])
app.include_router(publish.router, prefix="/publish", tags=["publish"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(series.router, prefix="/series", tags=["series"])

# Serve rendered mp4s (and the intermediate assets that produced them) at
# /renders/{package_id}/out.mp4 — lets the frontend preview without piping
# video bytes through the API handler.
renders_dir = Path(settings.renders_dir).resolve()
renders_dir.mkdir(parents=True, exist_ok=True)
app.mount("/renders", StaticFiles(directory=str(renders_dir)), name="renders")
