"""Measurement endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentBridge, CurrentPrincipal, DbSession
from app.core.timeutil import epoch_to_utc_naive
from app.models.measurement import Measurement
from app.models.sensor import Sensor
from app.schemas.common import ErrorResponse, Page
from app.schemas.measurement import MeasurementCreate, MeasurementRead

router = APIRouter(prefix="/measurements", tags=["measurements"])

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


def _ensure_sensor(db: Session, sensor_id: str, bridge_id: str) -> None:
    """Register a measuring station the first time it reports a reading.

    First writer wins: if ``sensor_id`` is already registered (possibly under
    another bridge) the existing row is kept untouched. A concurrent insert is
    tolerated by rolling back after the integrity error.
    """
    if db.scalar(select(Sensor).where(Sensor.sensor_id == sensor_id)) is not None:
        return
    db.add(Sensor(sensor_id=sensor_id, bridge_id=bridge_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


@router.post(
    "",
    response_model=MeasurementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Store a rainfall measurement",
    response_description="The stored measurement.",
    responses={
        status.HTTP_200_OK: {
            "model": MeasurementRead,
            "description": "Duplicate (same sensor_id and sent_at); the existing row is returned.",
        },
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Missing API key."},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Invalid bridge key."},
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "The same sensor_id and sent_at already exists for another bridge.",
        },
    },
)
def create_measurement(
    payload: MeasurementCreate,
    db: DbSession,
    bridge: CurrentBridge,
    response: Response,
) -> Measurement:
    """Persist one reading for the authenticated bridge.

    Writes are idempotent: a retransmitted packet (same ``sensor_id`` and
    ``sent_at``) returns ``200`` with the already-stored row instead of
    creating a duplicate. The sensor is registered on first sight.
    """
    _ensure_sensor(db, payload.sensor_id, bridge.bridge_id)
    measurement = Measurement(
        bridge_id=bridge.bridge_id,
        sensor_id=payload.sensor_id,
        value_mm=payload.value_mm,
        sent_at=epoch_to_utc_naive(payload.sent_at),
    )
    db.add(measurement)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(Measurement).where(
                Measurement.sensor_id == payload.sensor_id,
                Measurement.sent_at == measurement.sent_at,
            )
        )
        if existing is None:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not store the measurement.",
            ) from None
        if existing.bridge_id != bridge.bridge_id:
            # (sensor_id, sent_at) is unique across all bridges, so a clash can
            # also mean another bridge owns this reading. Never return it.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A measurement with the same sensor_id and sent_at already exists.",
            ) from None
        response.status_code = status.HTTP_200_OK
        return existing

    db.refresh(measurement)
    return measurement


@router.get(
    "",
    response_model=Page[MeasurementRead],
    summary="List measurements",
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
def list_measurements(
    principal: CurrentPrincipal,
    db: DbSession,
    bridge_id: str | None = Query(None, description="Filter by bridge (admin only)."),
    sensor_id: str | None = Query(None, description="Filter by sensor."),
    sent_from: int | None = Query(None, ge=0, description="Epoch seconds, inclusive lower bound."),
    sent_to: int | None = Query(None, ge=0, description="Epoch seconds, inclusive upper bound."),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> Page[MeasurementRead]:
    """List measurements.

    A bridge only ever sees its own rows; the admin sees every bridge and may
    additionally filter with ``bridge_id``.
    """
    stmt = select(Measurement)
    if not principal.is_admin:
        stmt = stmt.where(Measurement.bridge_id == principal.bridge_id)
    elif bridge_id:
        stmt = stmt.where(Measurement.bridge_id == bridge_id)

    if sensor_id:
        stmt = stmt.where(Measurement.sensor_id == sensor_id)
    if sent_from is not None:
        stmt = stmt.where(Measurement.sent_at >= epoch_to_utc_naive(sent_from))
    if sent_to is not None:
        stmt = stmt.where(Measurement.sent_at <= epoch_to_utc_naive(sent_to))

    stmt = (
        stmt.order_by(Measurement.sent_at.desc(), Measurement.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    rows = list(db.scalars(stmt))
    has_more = len(rows) > limit
    items = rows[:limit]
    return Page(items=items, limit=limit, offset=offset, count=len(items), has_more=has_more)


@router.get(
    "/{measurement_id}",
    response_model=MeasurementRead,
    summary="Get a single measurement",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Not found."},
    },
)
def get_measurement(
    db: DbSession,
    principal: CurrentPrincipal,
    measurement_id: int = Path(ge=1),
) -> Measurement:
    """Return one measurement the caller is allowed to see."""
    measurement = db.get(Measurement, measurement_id)
    if measurement is None or (
        not principal.is_admin and measurement.bridge_id != principal.bridge_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Measurement not found.")
    return measurement
