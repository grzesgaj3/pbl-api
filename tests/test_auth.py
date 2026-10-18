"""Authentication and authorisation tests."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.bridge import Bridge

PROTECTED = "/api/v1/measurements"


def test_missing_key_returns_401_with_challenge(client):
    response = client.get(PROTECTED)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "ApiKey"
    assert response.json()["error"]["code"] == "unauthorized"


def test_missing_key_on_admin_endpoint_returns_401(client):
    response = client.post(
        "/api/v1/commands",
        json={"bridge_id": "x", "sensor_id": "s"},
    )
    assert response.status_code == 401


def test_bridge_key_cannot_use_admin_endpoints(client, bridge):
    response = client.post(
        "/api/v1/commands",
        json={"bridge_id": bridge.bridge_id, "sensor_id": "sensor1"},
        headers=bridge.headers,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_deactivated_bridge_is_rejected(client, bridge):
    with SessionLocal() as db:
        stored = db.scalar(select(Bridge).where(Bridge.bridge_id == bridge.bridge_id))
        stored.is_active = False
        db.commit()

    response = client.get(PROTECTED, headers=bridge.headers)
    assert response.status_code == 403


@pytest.mark.parametrize("path", [PROTECTED, "/api/v1/commands"])
def test_empty_key_is_rejected(client, path):
    response = client.get(path, headers={"X-API-Key": ""})
    assert response.status_code == 401
