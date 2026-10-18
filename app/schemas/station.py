"""Station (bridge / sensor) response schemas.

Both payloads are read-only and admin-facing. The bridge key hash is never
part of a response.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from app.core.timeutil import isoformat_utc


class BridgeRead(BaseModel):
    """A registered bridge (LoRa receiver / receiving station)."""

    model_config = ConfigDict(from_attributes=True)

    bridge_id: str
    is_active: bool
    created_at: datetime
    last_seen_at: datetime | None

    @field_serializer("created_at", "last_seen_at")
    def _serialize_time(self, value: datetime | None) -> str | None:
        return None if value is None else isoformat_utc(value)


class SensorRead(BaseModel):
    """A registered measuring station and statistics derived from readings.

    ``last_measurement_at`` is the database time the most recent reading was
    stored; ``measurement_count`` counts every stored reading for the sensor.
    """

    model_config = ConfigDict(from_attributes=True)

    sensor_id: str
    bridge_id: str
    created_at: datetime
    last_measurement_at: datetime | None
    measurement_count: int

    @field_serializer("created_at", "last_measurement_at")
    def _serialize_time(self, value: datetime | None) -> str | None:
        return None if value is None else isoformat_utc(value)
