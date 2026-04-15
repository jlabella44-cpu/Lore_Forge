from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import analytics, books, discover, generate, publish
from app.scheduler import scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
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
