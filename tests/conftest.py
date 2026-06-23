"""Shared pytest fixtures.

Each test run uses a temporary SQLite database and forces demo mode
(MOCK_LLM + mock embeddings) so the suite needs no network or API keys.
"""
from __future__ import annotations

import os
import tempfile

import pytest

# Force fully-offline demo mode BEFORE app modules import settings.
os.environ.setdefault("MOCK_LLM", "true")
os.environ.setdefault("USE_MOCK_EMBEDDINGS", "true")
_tmp_db = os.path.join(tempfile.gettempdir(), "assistant_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.database import init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_db():
    if os.path.exists(_tmp_db):
        os.remove(_tmp_db)
    init_db()
    yield
    if os.path.exists(_tmp_db):
        os.remove(_tmp_db)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
