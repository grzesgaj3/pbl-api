"""Tests for the measurement seeding CLI."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.security import hash_api_key
from app.core.timeutil import epoch_to_utc_naive
from app.db.session import SessionLocal
from app.models.bridge import Bridge
from app.models.measurement import Measurement
from app.models.sensor import Sensor
from app.scripts import seed_measurements as cli

END = 1_729_260_000  # fixed epoch anchor: deterministic windows in tests


def _seed(creds, *args):
    # ``--api-key=KEY`` (equals form) because url-safe keys may start with '-'.
    return cli.main([f"--api-key={creds.api_key}", "--end", str(END), *args])


def _snapshot():
    with SessionLocal() as db:
        total = db.scalar(select(func.count(Measurement.id)))
        per_sensor = dict(
            db.execute(
                select(Measurement.sensor_id, func.count()).group_by(Measurement.sensor_id)
            ).all()
        )
        per_bridge = dict(
            db.execute(
                select(Measurement.bridge_id, func.count()).group_by(Measurement.bridge_id)
            ).all()
        )
        sensors = list(db.scalars(select(Sensor.sensor_id).order_by(Sensor.sensor_id)))
    return total, per_sensor, per_bridge, sensors


# --- argument / bridge resolution ------------------------------------------


def test_missing_api_key_is_a_usage_error(client, monkeypatch):
    monkeypatch.delenv("PBL_BRIDGE_KEY", raising=False)
    with pytest.raises(SystemExit):
        cli.main([])


def test_unknown_key_exits(client):
    with pytest.raises(SystemExit, match="No active bridge"):
        cli.main(["--api-key=nope"])


def test_inactive_bridge_exits(client, bridge, db):
    record = db.scalar(select(Bridge).where(Bridge.bridge_id == bridge.bridge_id))
    record.is_active = False
    db.commit()

    with pytest.raises(SystemExit, match="No active bridge"):
        cli.main([f"--api-key={bridge.api_key}"])


def test_key_may_start_with_a_dash(client, db):
    key = "-" + "a" * 42  # url-safe keys can begin with a dash
    db.add(Bridge(bridge_id="dashmostek", api_key_hash=hash_api_key(key), is_active=True))
    db.commit()

    assert cli.main([f"--api-key={key}", "--end", str(END), "--count", "5"]) == 0

    _, _, per_bridge, _ = _snapshot()
    assert per_bridge == {"dashmostek": 5}


def test_key_can_come_from_the_environment(client, bridge, monkeypatch):
    monkeypatch.setenv("PBL_BRIDGE_KEY", bridge.api_key)

    assert cli.main(["--end", str(END), "--count", "5"]) == 0

    _, _, per_bridge, _ = _snapshot()
    assert per_bridge == {bridge.bridge_id: 5}


# --- seeding ---------------------------------------------------------------


def test_seeds_requested_readings_and_registers_sensor(client, bridge):
    assert _seed(bridge, "--count", "50", "--sensors", "1") == 0

    total, per_sensor, per_bridge, sensors = _snapshot()
    assert total == 50
    assert per_sensor == {"sensor1": 50}
    assert sensors == ["sensor1"]
    assert per_bridge == {bridge.bridge_id: 50}


def test_distributes_readings_across_sensors(client, bridge):
    _seed(bridge, "--count", "40", "--sensors", "4")

    total, per_sensor, _, sensors = _snapshot()
    assert total == 40
    assert sorted(per_sensor) == ["sensor1", "sensor2", "sensor3", "sensor4"]
    assert set(per_sensor.values()) == {10}
    assert len(sensors) == 4


def test_rerun_with_same_window_does_not_duplicate(client, bridge):
    _seed(bridge, "--count", "30", "--sensors", "3")
    _seed(bridge, "--count", "30", "--sensors", "3")

    total, _, _, _ = _snapshot()
    assert total == 30


def test_only_touches_the_given_bridge(client, bridge, other_bridge):
    _seed(bridge, "--count", "20", "--sensors", "1")

    _, _, per_bridge, _ = _snapshot()
    assert per_bridge == {bridge.bridge_id: 20}


def test_values_are_realistic_millimetres(client, bridge):
    _seed(bridge, "--count", "50", "--sensors", "1")

    with SessionLocal() as db:
        values = list(db.scalars(select(Measurement.value_mm)))
    assert all(Decimal("0") <= value <= Decimal("50") for value in values)


# --- pure generator --------------------------------------------------------


def test_generate_readings_is_deterministic_for_a_seed():
    first = cli.generate_readings(count=10, sensors=["sensor1"], step=60, end=END, seed=7)
    second = cli.generate_readings(count=10, sensors=["sensor1"], step=60, end=END, seed=7)
    assert first == second
    assert first != cli.generate_readings(count=10, sensors=["sensor1"], step=60, end=END, seed=8)


def test_generate_readings_spreads_timestamps_across_the_window():
    readings = cli.generate_readings(count=5, sensors=["sensor1"], step=120, end=END, seed=1)

    assert [r.sent_at for r in readings] == sorted(r.sent_at for r in readings)
    assert readings[-1].sent_at == epoch_to_utc_naive(END)
    assert readings[0].sent_at == epoch_to_utc_naive(END - 4 * 120)
