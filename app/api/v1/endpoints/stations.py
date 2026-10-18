"""Station endpoints: read-only lists of bridges and sensors (admin only).

These feed the separate admin panel: it needs the registered bridges and
measuring stations to choose from before it posts a cleaning command and to
interpret measurements. Nothing here leaks a secret — the bridge API-key hash
is never returned.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.deps import AdminPrincipal, DbSession
from app.models.bridge import Bridge
from app.models.measurement import Measurement
from app.models.sensor import Sensor
from app.schemas.common import ErrorResponse, Page
from app.schemas.station import BridgeRead, SensorRead

router = APIRouter(tags=["stations"])

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000

_ADMIN_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Missing API key."},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Admin key required."},
}


@router.get(
    "/bridges",
    response_model=Page[BridgeRead],
    summary="List bridge stations (admin)",
    description="Registered bridge stations, ordered by ``bridge_id``.",
    responses=_ADMIN_RESPONSES,
)
def list_bridges(
    db: DbSession,
    _admin: AdminPrincipal,
    is_active: bool | None = Query(None, description="Filter by activation flag."),
    q: str | None = Query(None, description="Case-insensitive substring of bridge_id."),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> Page[BridgeRead]:
    """Return registered bridges; a bridge key is rejected with ``403``."""
    stmt = select(Bridge)
    if is_active is not None:
        stmt = stmt.where(Bridge.is_active.is_(is_active))
    if q:
        stmt = stmt.where(Bridge.bridge_id.like(f"%{q}%"))

    stmt = stmt.order_by(Bridge.bridge_id).offset(offset).limit(limit + 1)
    rows = list(db.scalars(stmt))
    has_more = len(rows) > limit
    items = rows[:limit]
    return Page(items=items, limit=limit, offset=offset, count=len(items), has_more=has_more)


@router.get(
    "/sensors",
    response_model=Page[SensorRead],
    summary="List measuring stations (admin)",
    description="Registered sensors, ordered by ``sensor_id``; filter with ``bridge_id``.",
    responses=_ADMIN_RESPONSES,
)
def list_sensors(
    db: DbSession,
    _admin: AdminPrincipal,
    bridge_id: str | None = Query(None, description="Filter by the bridge that reported it."),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> Page[SensorRead]:
    """Return registered sensors with a reading count and last-seen time."""
    stats = (
        select(
            Measurement.sensor_id.label("sensor_id"),
            func.max(Measurement.recorded_at).label("last_measurement_at"),
            func.count(Measurement.id).label("measurement_count"),
        )
        .group_by(Measurement.sensor_id)
        .subquery()
    )

    stmt = (
        select(
            Sensor.sensor_id,
            Sensor.bridge_id,
            Sensor.created_at,
            stats.c.last_measurement_at,
            func.coalesce(stats.c.measurement_count, 0).label("measurement_count"),
        )
        .outerjoin(stats, stats.c.sensor_id == Sensor.sensor_id)
        .order_by(Sensor.sensor_id)
        .offset(offset)
        .limit(limit + 1)
    )
    if bridge_id:
        stmt = stmt.where(Sensor.bridge_id == bridge_id)

    rows = list(db.execute(stmt))
    has_more = len(rows) > limit
    items = rows[:limit]
    return Page(items=items, limit=limit, offset=offset, count=len(items), has_more=has_more)
