from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.routers import analytics, books, discover, generate, publish
from app.scheduler import register_jobs, scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    register_jobs()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


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
app.include_router(books.router, prefix="/books", tags=["books"])
app.include_router(generate.router, tags=["generate"])
app.include_router(publish.router, prefix="/publish", tags=["publish"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])

# Serve rendered mp4s (and the intermediate assets that produced them) at
# /renders/{package_id}/out.mp4 — lets the frontend preview without piping
# video bytes through the API handler.
renders_dir = Path(settings.renders_dir).resolve()
renders_dir.mkdir(parents=True, exist_ok=True)
app.mount("/renders", StaticFiles(directory=str(renders_dir)), name="renders")
