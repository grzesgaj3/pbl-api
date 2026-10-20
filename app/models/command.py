from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import PRIMARY_KEY_TYPE, Base


class CommandStatus(enum.StrEnum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"


class Command(Base):
    __tablename__ = "commands"
    __table_args__ = (
        Index("ix_commands_bridge_status_created", "bridge_id", "status", "created_at"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    bridge_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("bridges.bridge_id"), nullable=False
    )
    sensor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    command_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="clean", server_default="clean"
    )
    payload: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CommandStatus] = mapped_column(
        Enum(CommandStatus, name="command_status", native_enum=True),
        nullable=False,
        default=CommandStatus.PENDING,
        server_default=CommandStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
