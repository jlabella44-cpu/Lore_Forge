from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine_kwargs: dict = {}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


if settings.database_url.startswith("sqlite"):
    # SQLite can't handle concurrent writers by default. WAL mode allows
    # concurrent reads during a single writer (good enough for our
    # request/cost-record split) and busy_timeout gives a new writer 30s to
    # wait on an existing lock instead of erroring out immediately.
    #
    # Both apply to every new connection — WAL persists at the file level
    # so subsequent processes inherit it.
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, connection_record):  # pragma: no cover
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Dev convenience: ensure the sqlite file exists. Real schema lives in Alembic."""
    # Importing models registers them on Base.metadata so alembic autogenerate can see them.
    from app import models  # noqa: F401


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
