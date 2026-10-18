"""Bridge (LoRa gateway/receiver) model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Bridge(Base):
    """A bridge station: the LoRa receiver that forwards measurements.

    Each bridge authenticates with its own API key; only the key's hash is
    stored. ``bridge_id`` is the human-readable station identifier and is
    used as the foreign key from measurements and commands.
    """

    __tablename__ = "bridges"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bridge_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Bridge bridge_id={self.bridge_id!r} active={self.is_active}>"
