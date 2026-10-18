"""Command request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.core.timeutil import isoformat_utc
from app.models.command import CommandStatus


class CommandCreate(BaseModel):
    """Admin request to clean a single sensor behind a bridge."""

    bridge_id: str = Field(min_length=1, max_length=64, examples=["mostek1"])
    sensor_id: str = Field(min_length=1, max_length=64, examples=["sensor1"])
    command_type: Literal["clean"] = "clean"


class CommandReject(BaseModel):
    """Optional reason supplied by a bridge when it rejects a command."""

    note: str | None = Field(default=None, max_length=255)


class CommandRead(BaseModel):
    """A cleaning command and its current state."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    bridge_id: str
    sensor_id: str | None
    command_type: str
    payload: str
    status: CommandStatus
    created_at: datetime
    responded_at: datetime | None
    response_note: str | None

    @field_serializer("created_at", "responded_at")
    def _serialize_time(self, value: datetime | None) -> str | None:
        return None if value is None else isoformat_utc(value)
