from __future__ import annotations

from datetime import UTC, datetime


def epoch_to_utc_naive(epoch_seconds: int) -> datetime:
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).replace(tzinfo=None)


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def isoformat_utc(value: datetime) -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat().replace("+00:00", "Z")
