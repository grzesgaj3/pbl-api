"""Station (bridge / sensor) endpoint tests."""

from __future__ import annotations

from sqlalchemy import select

from app.models.bridge import Bridge
from app.models.sensor import Sensor

SENT_AT = 1_729_260_000


def _payload(**overrides):
    data = {"sensor_id": "sensor1", "value_mm": 3.4, "sent_at": SENT_AT}
    data.update(overrides)
    return data


def _post_measurement(client, creds, **overrides):
    return client.post("/api/v1/measurements", json=_payload(**overrides), headers=creds.headers)


# --- authorisation ---------------------------------------------------------


def test_bridges_requires_key(client):
    response = client.get("/api/v1/bridges")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_sensors_requires_key(client):
    assert client.get("/api/v1/sensors").status_code == 401


def test_bridges_rejects_bridge_key(client, bridge):
    assert client.get("/api/v1/bridges", headers=bridge.headers).status_code == 403


def test_sensors_rejects_bridge_key(client, bridge):
    assert client.get("/api/v1/sensors", headers=bridge.headers).status_code == 403


# --- bridges ---------------------------------------------------------------


def test_admin_lists_registered_bridges(client, bridge, other_bridge, admin_headers):
    body = client.get("/api/v1/bridges", headers=admin_headers).json()
    assert body["count"] == 2
    assert body["has_more"] is False
    assert [item["bridge_id"] for item in body["items"]] == ["mostek1", "mostek2"]
    first = body["items"][0]
    assert first["is_active"] is True
    assert first["last_seen_at"] is None
    assert first["created_at"].endswith("Z")


def test_bridges_payload_never_leaks_key_hash(client, bridge, admin_headers):
    response = client.get("/api/v1/bridges", headers=admin_headers)
    assert response.status_code == 200
    assert "api_key_hash" not in response.text


def test_bridges_last_seen_refreshes_after_activity(client, bridge, admin_headers):
    _post_measurement(client, bridge)

    body = client.get("/api/v1/bridges", headers=admin_headers).json()
    assert body["items"][0]["last_seen_at"] is not None


def test_bridges_filters_by_active_flag(client, bridge, admin_headers, db):
    record = db.scalar(select(Bridge).where(Bridge.bridge_id == bridge.bridge_id))
    record.is_active = False
    db.commit()

    inactive = client.get("/api/v1/bridges?is_active=false", headers=admin_headers).json()
    assert inactive["count"] == 1
    assert inactive["items"][0]["is_active"] is False

    active = client.get("/api/v1/bridges?is_active=true", headers=admin_headers).json()
    assert active["count"] == 0


def test_bridges_substring_filter(client, bridge, other_bridge, admin_headers):
    body = client.get("/api/v1/bridges?q=mostek2", headers=admin_headers).json()
    assert body["count"] == 1
    assert body["items"][0]["bridge_id"] == "mostek2"


def test_bridges_pagination(client, make_bridge, admin_headers):
    for index in range(3):
        make_bridge(f"mostek{index}")

    first_page = client.get("/api/v1/bridges?limit=2", headers=admin_headers).json()
    assert first_page["count"] == 2
    assert first_page["has_more"] is True

    second_page = client.get("/api/v1/bridges?limit=2&offset=2", headers=admin_headers).json()
    assert second_page["count"] == 1
    assert second_page["has_more"] is False


# --- sensors ---------------------------------------------------------------


def test_sensors_empty_before_any_measurement(client, admin_headers):
    body = client.get("/api/v1/sensors", headers=admin_headers).json()
    assert body["count"] == 0
    assert body["items"] == []


def test_measurement_registers_sensor(client, bridge, admin_headers):
    _post_measurement(client, bridge)

    body = client.get("/api/v1/sensors", headers=admin_headers).json()
    assert body["count"] == 1
    sensor = body["items"][0]
    assert sensor["sensor_id"] == "sensor1"
    assert sensor["bridge_id"] == bridge.bridge_id
    assert sensor["measurement_count"] == 1
    assert sensor["last_measurement_at"] is not None
    assert sensor["created_at"].endswith("Z")


def test_repeated_measurements_keep_one_sensor_row(client, bridge, admin_headers):
    _post_measurement(client, bridge)
    _post_measurement(client, bridge, sent_at=SENT_AT + 1)

    body = client.get("/api/v1/sensors", headers=admin_headers).json()
    assert body["count"] == 1
    assert body["items"][0]["measurement_count"] == 2


def test_duplicate_measurement_does_not_double_count(client, bridge, admin_headers):
    _post_measurement(client, bridge)
    _post_measurement(client, bridge)  # idempotent retransmission

    body = client.get("/api/v1/sensors", headers=admin_headers).json()
    assert body["items"][0]["measurement_count"] == 1


def test_sensors_are_mapped_to_their_bridge(client, bridge, other_bridge, admin_headers):
    _post_measurement(client, bridge, sensor_id="sensor1")
    _post_measurement(client, other_bridge, sensor_id="sensor2")

    body = client.get("/api/v1/sensors", headers=admin_headers).json()
    mapping = {item["sensor_id"]: item["bridge_id"] for item in body["items"]}
    assert mapping == {"sensor1": bridge.bridge_id, "sensor2": other_bridge.bridge_id}


def test_sensors_can_be_filtered_by_bridge(client, bridge, other_bridge, admin_headers):
    _post_measurement(client, bridge, sensor_id="sensor1")
    _post_measurement(client, other_bridge, sensor_id="sensor2")

    body = client.get(
        f"/api/v1/sensors?bridge_id={other_bridge.bridge_id}", headers=admin_headers
    ).json()
    assert body["count"] == 1
    assert body["items"][0]["sensor_id"] == "sensor2"
    assert body["items"][0]["bridge_id"] == other_bridge.bridge_id


def test_sensors_pagination(client, bridge, admin_headers):
    for index in range(3):
        _post_measurement(client, bridge, sensor_id=f"sensor{index}", sent_at=SENT_AT + index)

    first_page = client.get("/api/v1/sensors?limit=2", headers=admin_headers).json()
    assert first_page["count"] == 2
    assert first_page["has_more"] is True

    second_page = client.get("/api/v1/sensors?limit=2&offset=2", headers=admin_headers).json()
    assert second_page["count"] == 1
    assert second_page["has_more"] is False


def test_sensor_registry_survives_measurement_visibility(client, bridge, admin_headers):
    """A bridge key cannot see sensors, but registration still happened."""
    _post_measurement(client, bridge)

    assert client.get("/api/v1/sensors", headers=bridge.headers).status_code == 403
    assert client.get("/api/v1/sensors", headers=admin_headers).json()["count"] == 1


def test_sensor_without_readings_reports_zero(client, bridge, admin_headers, db):
    db.add(Sensor(sensor_id="sensor9", bridge_id=bridge.bridge_id))
    db.commit()

    body = client.get("/api/v1/sensors", headers=admin_headers).json()
    assert body["count"] == 1
    sensor = body["items"][0]
    assert sensor["sensor_id"] == "sensor9"
    assert sensor["measurement_count"] == 0
    assert sensor["last_measurement_at"] is None
