"""Measurement request/response schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.core.timeutil import isoformat_utc


class MeasurementCreate(BaseModel):
    """Payload a bridge posts for a single rainfall reading.

    ``bridge_id`` is intentionally absent: it is taken from the authenticated
    API key so a bridge can only write data for itself.
    """

    sensor_id: str = Field(min_length=1, max_length=64, examples=["sensor1"])
    value_mm: Decimal = Field(
        ge=0,
        le=9999.99,
        max_digits=6,
        decimal_places=2,
        examples=[3.4],
        description="Rainfall in millimetres.",
    )
    sent_at: int = Field(
        ge=0,
        examples=[1729260000],
        description="Device transmit time as epoch seconds (UTC).",
    )

    @field_validator("sensor_id")
    @classmethod
    def _clean_sensor_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("sensor_id must not be blank")
        return cleaned


class MeasurementRead(BaseModel):
    """A stored measurement."""

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
