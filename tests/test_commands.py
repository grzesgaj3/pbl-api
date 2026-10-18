"""Cleaning-command endpoint tests."""

from __future__ import annotations


def _create(client, admin_headers, bridge_id, sensor_id="sensor1"):
    return client.post(
        "/api/v1/commands",
        json={"bridge_id": bridge_id, "sensor_id": sensor_id, "command_type": "clean"},
        headers=admin_headers,
    )


def test_only_admin_can_create_command(client, bridge):
    response = _create(client, bridge.headers, bridge.bridge_id)
    assert response.status_code == 403


def test_admin_creates_command_with_generated_payload(client, bridge, admin_headers):
    response = _create(client, admin_headers, bridge.bridge_id)
    assert response.status_code == 201
    body = response.json()
    assert body["bridge_id"] == bridge.bridge_id
    assert body["sensor_id"] == "sensor1"
    assert body["command_type"] == "clean"
    assert body["payload"] == "sensor1;clean;"
    assert body["status"] == "PENDING"
    assert body["responded_at"] is None


def test_create_command_for_unknown_bridge_returns_404(client, admin_headers):
    response = _create(client, admin_headers, "ghost")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_bridge_polls_only_its_pending_commands(client, bridge, other_bridge, admin_headers):
    _create(client, admin_headers, bridge.bridge_id, "sensor1")
    _create(client, admin_headers, other_bridge.bridge_id, "sensor9")

    response = client.get("/api/v1/commands?status=PENDING", headers=bridge.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["payload"] == "sensor1;clean;"

    admin_view = client.get("/api/v1/commands", headers=admin_headers).json()
    assert admin_view["count"] == 2


def test_acknowledge_command(client, bridge, admin_headers):
    command_id = _create(client, admin_headers, bridge.bridge_id).json()["id"]

    response = client.post(f"/api/v1/commands/{command_id}/ack", headers=bridge.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACKNOWLEDGED"
    assert body["responded_at"] is not None


def test_acknowledging_twice_conflicts(client, bridge, admin_headers):
    command_id = _create(client, admin_headers, bridge.bridge_id).json()["id"]
    client.post(f"/api/v1/commands/{command_id}/ack", headers=bridge.headers)

    response = client.post(f"/api/v1/commands/{command_id}/ack", headers=bridge.headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_reject_command_records_note(client, bridge, admin_headers):
    command_id = _create(client, admin_headers, bridge.bridge_id).json()["id"]

    response = client.post(
        f"/api/v1/commands/{command_id}/reject",
        json={"note": "sensor offline"},
        headers=bridge.headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REJECTED"
    assert body["response_note"] == "sensor offline"


def test_other_bridge_cannot_answer_command(client, bridge, other_bridge, admin_headers):
    command_id = _create(client, admin_headers, bridge.bridge_id).json()["id"]

    response = client.post(f"/api/v1/commands/{command_id}/ack", headers=other_bridge.headers)
    assert response.status_code == 404


def test_admin_can_read_single_command(client, bridge, admin_headers):
    command_id = _create(client, admin_headers, bridge.bridge_id).json()["id"]
    response = client.get(f"/api/v1/commands/{command_id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == command_id
