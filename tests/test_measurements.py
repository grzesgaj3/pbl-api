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


def test_duplicate_across_bridges_never_leaks(client, bridge, other_bridge):
    client.post("/api/v1/measurements", json=_payload(), headers=bridge.headers)

    response = client.post("/api/v1/measurements", json=_payload(), headers=other_bridge.headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert bridge.bridge_id not in response.text


def test_blank_sensor_id_is_rejected(client, bridge):
    response = client.post(
        "/api/v1/measurements", json=_payload(sensor_id="   "), headers=bridge.headers
    )
    assert response.status_code == 422


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


def test_list_filters_by_sensor(client, bridge, other_bridge, admin_headers):
    client.post("/api/v1/measurements", json=_payload(), headers=bridge.headers)
    client.post(
        "/api/v1/measurements",
        json=_payload(sensor_id="sensor2"),
        headers=other_bridge.headers,
    )

    body = client.get("/api/v1/measurements?sensor_id=sensor2", headers=admin_headers).json()
    assert body["count"] == 1
    assert body["items"][0]["sensor_id"] == "sensor2"


def test_pagination_reports_more_rows(client, bridge, admin_headers):
    for index in range(3):
        client.post(
            "/api/v1/measurements",
            json=_payload(sensor_id=f"sensor{index}", sent_at=SENT_AT + index),
            headers=bridge.headers,
        )

    first_page = client.get("/api/v1/measurements?limit=2", headers=admin_headers).json()
    assert first_page["count"] == 2
    assert first_page["has_more"] is True

    second_page = client.get("/api/v1/measurements?limit=2&offset=2", headers=admin_headers).json()
    assert second_page["count"] == 1
    assert second_page["has_more"] is False


def test_get_measurement_hidden_from_other_bridge(client, bridge, other_bridge):
    created = client.post("/api/v1/measurements", json=_payload(), headers=bridge.headers).json()

    mine = client.get(f"/api/v1/measurements/{created['id']}", headers=bridge.headers)
    assert mine.status_code == 200

    theirs = client.get(f"/api/v1/measurements/{created['id']}", headers=other_bridge.headers)
    assert theirs.status_code == 404


def test_admin_can_read_any_measurement(client, bridge, other_bridge, admin_headers):
    created = client.post("/api/v1/measurements", json=_payload(), headers=bridge.headers).json()

    response = client.get(f"/api/v1/measurements/{created['id']}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["bridge_id"] == bridge.bridge_id


def test_get_missing_measurement_returns_404(client, admin_headers):
    assert client.get("/api/v1/measurements/999", headers=admin_headers).status_code == 404
