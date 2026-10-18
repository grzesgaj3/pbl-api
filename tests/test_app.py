"""App factory and middleware tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_unknown_route_uses_the_error_envelope(client):
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_method_not_allowed_envelope(client, bridge):
    response = client.delete("/api/v1/measurements", headers=bridge.headers)
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_cors_headers_when_origins_configured():
    app = create_app(settings=Settings(cors_origins="https://example.com"))
    with TestClient(app) as test_client:
        response = test_client.get("/health", headers={"Origin": "https://example.com"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://example.com"


def test_docs_can_be_disabled():
    app = create_app(settings=Settings(enable_docs=False))
    with TestClient(app) as test_client:
        assert test_client.get("/docs").status_code == 404
        assert test_client.get("/openapi.json").status_code == 404
