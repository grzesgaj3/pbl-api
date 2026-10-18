"""Measurement endpoint tests."""

from __future__ import annotations

SENT_AT = 1_729_260_000


def _payload(**overrides):
    data = {"sensor_id": "sensor1", "value_mm": 3.4, "sent_at": SENT_AT}
    data.update(overrides)
    return data


def test_create_measurement_requires_key(client):
    response = client.post("/api/v1/measurements", json=_payload())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_create_measurement_rejects_unknown_key(client):
    response = client.post("/api/v1/measurements", json=_payload(), headers={"X-API-Key": "nope"})
    assert response.status_code == 403


def test_create_measurement_stores_row(client, bridge):
    response = client.post("/api/v1/measurements", json=_payload(), headers=bridge.headers)
    assert response.status_code == 201
    body = response.json()
    assert body["bridge_id"] == bridge.bridge_id  # taken from the key, not the body
    assert body["sensor_id"] == "sensor1"
    assert body["value_mm"] == 3.4
    assert body["sent_at"] == "2024-10-18T14:00:00Z"
    assert body["recorded_at"].endswith("Z")
    assert body["id"] > 0


def test_duplicate_measurement_is_idempotent(client, bridge):
    first = client.post("/api/v1/measurements", json=_payload(), headers=bridge.headers)
    second = client.post("/api/v1/measurements", json=_payload(), headers=bridge.headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


def test_validation_error_envelope(client, bridge):
    response = client.post(
        "/api/v1/measurements",
        json=_payload(value_mm=-1),
        headers=bridge.headers,
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]


def test_bridge_lists_only_own_measurements(client, bridge, other_bridge):
    client.post("/api/v1/measurements", json=_payload(), headers=bridge.headers)
    client.post(
        "/api/v1/measurements",
        json=_payload(sensor_id="sensor2"),
        headers=other_bridge.headers,
    )

    own = client.get("/api/v1/measurements", headers=bridge.headers)
    assert own.status_code == 200
    body = own.json()
    assert body["count"] == 1
    assert body["items"][0]["bridge_id"] == bridge.bridge_id
    assert body["has_more"] is False


def test_admin_lists_everything_and_can_filter(client, bridge, other_bridge, admin_headers):
    client.post("/api/v1/measurements", json=_payload(), headers=bridge.headers)
    client.post(
        "/api/v1/measurements",
        json=_payload(sensor_id="sensor2"),
        headers=other_bridge.headers,
    )

    everything = client.get("/api/v1/measurements", headers=admin_headers).json()
    assert everything["count"] == 2

    filtered = client.get(
        f"/api/v1/measurements?bridge_id={other_bridge.bridge_id}", headers=admin_headers
    ).json()
    assert filtered["count"] == 1
    assert filtered["items"][0]["bridge_id"] == other_bridge.bridge_id


def test_list_filters_by_sent_window(client, bridge, admin_headers):
    client.post("/api/v1/measurements", json=_payload(), headers=bridge.headers)

    inside = client.get(
        f"/api/v1/measurements?sent_from={SENT_AT - 60}&sent_to={SENT_AT + 60}",
        headers=admin_headers,
    ).json()
    assert inside["count"] == 1

    outside = client.get(
        f"/api/v1/measurements?sent_from={SENT_AT + 1}", headers=admin_headers
    ).json()
    assert outside["count"] == 0


def test_get_measurement_hidden_from_other_bridge(client, bridge, other_bridge):
    created = client.post("/api/v1/measurements", json=_payload(), headers=bridge.headers).json()

    mine = client.get(f"/api/v1/measurements/{created['id']}", headers=bridge.headers)
    assert mine.status_code == 200

    theirs = client.get(f"/api/v1/measurements/{created['id']}", headers=other_bridge.headers)
    assert theirs.status_code == 404


def test_get_missing_measurement_returns_404(client, admin_headers):
    assert client.get("/api/v1/measurements/999", headers=admin_headers).status_code == 404
