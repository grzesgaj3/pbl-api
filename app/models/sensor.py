"""Sensor (measuring station) model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import PRIMARY_KEY_TYPE, Base


class Sensor(Base):
    """A measuring station: the individual rain gauge behind a bridge.

    The registry is populated automatically the first time a bridge posts a
    measurement for a given ``sensor_id`` (first writer wins), so a sensor only
    appears once it has reported at least one reading. ``created_at`` is when
    the sensor was first seen; the number and time of its readings are derived
    from ``measurements`` rather than stored here.
    """

    __tablename__ = "sensors"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    sensor_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    bridge_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("bridges.bridge_id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Sensor sensor_id={self.sensor_id!r} bridge={self.bridge_id!r}>"
