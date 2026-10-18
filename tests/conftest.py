"""Shared test fixtures.

Configuration is injected into the environment *before* importing anything
from ``app`` because the settings and the SQLAlchemy engine are built at
import time. Tests run against a throw-away SQLite file so no MariaDB is
needed.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="pbl-api-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP_DIR) / 'test.db'}"
os.environ["ADMIN_API_KEY"] = "test-admin-key-1234567890"
os.environ["LOG_LEVEL"] = "warning"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import generate_api_key, hash_api_key  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.bridge import Bridge  # noqa: E402

ADMIN_API_KEY = os.environ["ADMIN_API_KEY"]


@dataclass(frozen=True)
class BridgeCreds:
    """A registered bridge plus the plaintext key the tests may use."""

    bridge_id: str
    api_key: str

    @property
    def headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}


@pytest.fixture
def client():
    """TestClient with a fresh schema for every test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(client):
    """A direct session for arranging and asserting state."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def make_bridge(db):
    """Factory that registers a bridge and returns its credentials."""

    def _make(bridge_id: str = "mostek1") -> BridgeCreds:
        api_key = generate_api_key()
        db.add(Bridge(bridge_id=bridge_id, api_key_hash=hash_api_key(api_key), is_active=True))
        db.commit()
        return BridgeCreds(bridge_id=bridge_id, api_key=api_key)

    return _make


@pytest.fixture
def bridge(make_bridge) -> BridgeCreds:
    return make_bridge("mostek1")


@pytest.fixture
def other_bridge(make_bridge) -> BridgeCreds:
    return make_bridge("mostek2")


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-API-Key": ADMIN_API_KEY}
