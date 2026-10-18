"""Seed the database with synthetic rainfall readings for one bridge.

Usage::

    python -m app.scripts.seed_measurements --api-key=<BRIDGE_KEY> \
        [--sensors 3] [--count 500] [--days 7] [--seed 42]

The bridge is identified by its API key (it must already exist and be active);
the script never creates a bridge. The key may instead be supplied through the
``PBL_BRIDGE_KEY`` environment variable. Because url-safe keys can start with a
dash, pass the flag as ``--api-key=<KEY>`` (the ``=`` form) so argparse does not
mistake the key for an option. Readings are inserted directly into the
database and the ``sensors`` registry is filled in, so the admin station
listings show the seeded sensors. Re-running over the same time window skips
readings that are already stored, so it never trips the ``(sensor_id, sent_at)``
unique constraint.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import select

from app.core.security import hash_api_key
from app.core.timeutil import epoch_to_utc_naive
from app.db.session import SessionLocal
from app.models.bridge import Bridge
from app.models.measurement import Measurement
from app.models.sensor import Sensor

# About this share of readings is dry; the rest is a small rain episode.
_DRY_PROBABILITY = 0.7
_MAX_RAINFALL_MM = 15.0


class Reading(NamedTuple):
    """One synthetic reading, ready to become a ``Measurement`` row."""

    sensor_id: str
    sent_at: datetime
    value_mm: Decimal


def _rainfall(rng: random.Random) -> Decimal:
    """Return a plausible millimetre value: mostly dry, sometimes raining."""
    if rng.random() < _DRY_PROBABILITY:
        return Decimal("0.00")
    hundredths = rng.randint(1, int(_MAX_RAINFALL_MM * 100))
    return Decimal(hundredths) / 100


def generate_readings(
    *, count: int, sensors: list[str], step: int, end: int, seed: int
) -> list[Reading]:
    """Build ``count`` readings, oldest first, ending exactly at ``end``.

    Sensors are assigned round-robin and timestamps are evenly spaced by
    ``step`` seconds, so every ``(sensor_id, sent_at)`` pair is unique. The seed
    makes the series reproducible.
    """
    rng = random.Random(seed)
    readings: list[Reading] = []
    for index in range(count):
        sent_at = epoch_to_utc_naive(end - (count - 1 - index) * step)
        readings.append(Reading(sensors[index % len(sensors)], sent_at, _rainfall(rng)))
    return readings


def _ensure_sensors(db, bridge_id: str, sensors: list[str]) -> None:
    """Create any missing ``sensors`` registry rows (first writer wins)."""
    for sensor_id in sensors:
        if db.scalar(select(Sensor).where(Sensor.sensor_id == sensor_id)) is None:
            db.add(Sensor(sensor_id=sensor_id, bridge_id=bridge_id))
    db.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.scripts.seed_measurements",
        description="Insert synthetic rainfall readings for one bridge.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key of an active bridge. Use --api-key=KEY if it starts with "
        "'-', or set PBL_BRIDGE_KEY instead.",
    )
    parser.add_argument("--sensors", type=int, default=1, help="Number of sensors (1..N).")
    parser.add_argument("--count", type=int, default=500, help="Total readings to insert.")
    parser.add_argument("--days", type=int, default=7, help="Spread readings over the last N days.")
    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help="Epoch-seconds anchor for the window end (defaults to now).",
    )
    parser.add_argument("--prefix", default="sensor", help="Sensor id prefix.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducible values.")
    args = parser.parse_args(argv)

    if args.sensors < 1 or args.count < 1 or args.days < 1:
        parser.error("--sensors, --count and --days must be positive.")

    api_key = args.api_key or os.environ.get("PBL_BRIDGE_KEY")
    if not api_key:
        parser.error("--api-key is required (or set PBL_BRIDGE_KEY).")

    end = args.end if args.end is not None else int(time.time())
    step = max(1, (args.days * 86_400) // args.count)
    sensors = [f"{args.prefix}{index}" for index in range(1, args.sensors + 1)]

    readings = generate_readings(
        count=args.count, sensors=sensors, step=step, end=end, seed=args.seed
    )

    with SessionLocal() as db:
        bridge = db.scalar(
            select(Bridge).where(
                Bridge.api_key_hash == hash_api_key(api_key),
                Bridge.is_active.is_(True),
            )
        )
        if bridge is None:
            raise SystemExit("No active bridge matches that API key.")

        _ensure_sensors(db, bridge.bridge_id, sensors)

        window_start, window_end = readings[0].sent_at, readings[-1].sent_at
        existing = {
            (row.sensor_id, row.sent_at)
            for row in db.execute(
                select(Measurement.sensor_id, Measurement.sent_at).where(
                    Measurement.sensor_id.in_(sensors),
                    Measurement.sent_at >= window_start,
                    Measurement.sent_at <= window_end,
                )
            )
        }
        fresh = [r for r in readings if (r.sensor_id, r.sent_at) not in existing]

        db.add_all(
            Measurement(
                bridge_id=bridge.bridge_id,
                sensor_id=r.sensor_id,
                value_mm=r.value_mm,
                sent_at=r.sent_at,
            )
            for r in fresh
        )
        db.commit()
        bridge_id = bridge.bridge_id

    skipped = len(readings) - len(fresh)
    print(
        f"Bridge '{bridge_id}': inserted {len(fresh)} readings across "
        f"{len(sensors)} sensor(s) ({skipped} already present)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
