from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import PRIMARY_KEY_TYPE, Base


class Sensor(Base):
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
