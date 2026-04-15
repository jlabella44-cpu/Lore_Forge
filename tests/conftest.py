"""Shared fixtures: ephemeral SQLite DB + FastAPI TestClient."""
import os
import sys
from pathlib import Path

import pytest

# Put backend/ on sys.path before app imports.
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Force ephemeral sqlite for tests before anything in app loads.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as c:
        yield c
