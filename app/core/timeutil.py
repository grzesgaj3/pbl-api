"""Time conversion helpers.

Every timestamp the API stores is a *naive UTC* ``datetime``. Incoming device
times are epoch seconds; outgoing times are serialised as ISO 8601 with a
trailing ``Z``.
"""

from __future__ import annotations

from datetime import UTC, datetime


def epoch_to_utc_naive(epoch_seconds: int) -> datetime:
    """Convert epoch seconds to a naive UTC datetime (no tzinfo)."""
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).replace(tzinfo=None)


def utc_now_naive() -> datetime:
    """Return the current UTC time as a naive datetime."""
    return datetime.now(UTC).replace(tzinfo=None)


def isoformat_utc(value: datetime) -> str:
    """Render a naive UTC datetime as ISO 8601 with a ``Z`` suffix."""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat().replace("+00:00", "Z")
