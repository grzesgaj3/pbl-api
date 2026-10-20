from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from app.core.timeutil import isoformat_utc


class BridgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bridge_id: str
    is_active: bool
    created_at: datetime
    last_seen_at: datetime | None

    @field_serializer("created_at", "last_seen_at")
    def _serialize_time(self, value: datetime | None) -> str | None:
        return None if value is None else isoformat_utc(value)


class SensorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sensor_id: str
    bridge_id: str
    created_at: datetime
    last_measurement_at: datetime | None
    measurement_count: int

    @field_serializer("created_at", "last_measurement_at")
    def _serialize_time(self, value: datetime | None) -> str | None:
        return None if value is None else isoformat_utc(value)
