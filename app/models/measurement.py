from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import PRIMARY_KEY_TYPE, Base


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        UniqueConstraint("sensor_id", "sent_at", name="uq_measurements_sensor_sent"),
        Index("ix_measurements_bridge_sent", "bridge_id", "sent_at"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    bridge_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("bridges.bridge_id"), nullable=False
    )
    sensor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    value_mm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
