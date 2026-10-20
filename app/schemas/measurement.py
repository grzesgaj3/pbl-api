from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.core.timeutil import isoformat_utc


class MeasurementCreate(BaseModel):
    sensor_id: str = Field(min_length=1, max_length=64)
    value_mm: Decimal = Field(ge=0, le=9999.99, max_digits=6, decimal_places=2)
    sent_at: int = Field(ge=0)

    @field_validator("sensor_id")
    @classmethod
    def _clean_sensor_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("sensor_id must not be blank")
        return cleaned


class MeasurementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bridge_id: str
    sensor_id: str
    value_mm: Decimal
    sent_at: datetime
    recorded_at: datetime

    @field_serializer("value_mm")
    def _serialize_value(self, value: Decimal) -> float:
        return float(value)

    @field_serializer("sent_at", "recorded_at")
    def _serialize_time(self, value: datetime) -> str:
        return isoformat_utc(value)
