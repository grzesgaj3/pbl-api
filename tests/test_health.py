"""Health-check tests."""

from __future__ import annotations


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_readiness_checks_database(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
