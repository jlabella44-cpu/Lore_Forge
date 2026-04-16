"""Shared fixtures: ephemeral SQLite DB + FastAPI TestClient.

Uses an in-memory SQLite with StaticPool so the schema persists across the
connections a FastAPI request handler spawns. Overrides `get_db` so handlers
see the test session.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Put backend/ on sys.path before importing app.*
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Force ephemeral sqlite for tests before anything in app loads.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Redirect renders_dir + music_dir into a tmpdir before `main.py` is imported —
# otherwise FastAPI's `app.mount(..., StaticFiles(directory=renders_dir))` at
# import time creates the *real* repo-root renders/ folder every test run.
_TEST_RUN_TMP = Path(tempfile.mkdtemp(prefix="lore-forge-test-"))
os.environ.setdefault("RENDERS_DIR", str(_TEST_RUN_TMP / "renders"))
os.environ.setdefault("MUSIC_DIR", str(_TEST_RUN_TMP / "music"))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app import db as db_module
    from app.db import Base, get_db
    from main import app

    # Ensure models are registered on Base.metadata.
    from app import models  # noqa: F401

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(test_engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    # Stash + swap so other fixtures/modules see the test DB too.
    original_engine = db_module.engine
    original_session = db_module.SessionLocal
    db_module.engine = test_engine
    db_module.SessionLocal = TestSession
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
        db_module.engine = original_engine
        db_module.SessionLocal = original_session
