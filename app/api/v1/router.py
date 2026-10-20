"""API v1 routes: measurements, commands, stations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AdminPrincipal, CurrentBridge, CurrentPrincipal, DbSession
from app.core.timeutil import epoch_to_utc_naive, utc_now_naive
from app.models.bridge import Bridge
from app.models.command import Command, CommandStatus
from app.models.measurement import Measurement
from app.models.sensor import Sensor
from app.schemas.command import CommandCreate, CommandRead, CommandReject
from app.schemas.common import ErrorResponse, Page
from app.schemas.measurement import MeasurementCreate, MeasurementRead
from app.schemas.station import BridgeRead, SensorRead

router = APIRouter()
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


def _get_owned_command(db, command_id, bridge_id):
    command = db.get(Command, command_id)
    if command is None or command.bridge_id != bridge_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found.")
    return command


@router.post(
    "/measurements",
    response_model=MeasurementRead,
    status_code=status.HTTP_201_CREATED,
    tags=["measurements"],
    responses={
        status.HTTP_200_OK: {
            "model": MeasurementRead,
            "description": "Duplicate; existing row returned.",
        },
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def create_measurement(
    payload: MeasurementCreate, db: DbSession, bridge: CurrentBridge, response: Response
):
    if db.scalar(select(Sensor).where(Sensor.sensor_id == payload.sensor_id)) is None:
        db.add(Sensor(sensor_id=payload.sensor_id, bridge_id=bridge.bridge_id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()

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
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not store the measurement.",
            ) from None
        if existing.bridge_id != bridge.bridge_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A measurement with the same sensor_id and sent_at already exists.",
            ) from None
        response.status_code = status.HTTP_200_OK
        return existing

    db.refresh(measurement)
    return measurement


@router.get("/measurements", response_model=Page[MeasurementRead], tags=["measurements"])
def list_measurements(
    principal: CurrentPrincipal,
    db: DbSession,
    bridge_id: str | None = Query(None),
    sensor_id: str | None = Query(None),
    sent_from: int | None = Query(None, ge=0),
    sent_to: int | None = Query(None, ge=0),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
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


@router.get("/measurements/{measurement_id}", response_model=MeasurementRead, tags=["measurements"])
def get_measurement(db: DbSession, principal: CurrentPrincipal, measurement_id: int = Path(ge=1)):
    measurement = db.get(Measurement, measurement_id)
    if measurement is None or (
        not principal.is_admin and measurement.bridge_id != principal.bridge_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Measurement not found.")
    return measurement


@router.post(
    "/commands",
    response_model=CommandRead,
    status_code=status.HTTP_201_CREATED,
    tags=["commands"],
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    },
)
def create_command(payload: CommandCreate, db: DbSession, _admin: AdminPrincipal):
    bridge = db.scalar(select(Bridge).where(Bridge.bridge_id == payload.bridge_id))
    if bridge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Bridge '{payload.bridge_id}' not found."
        )
    command = Command(
        bridge_id=payload.bridge_id,
        sensor_id=payload.sensor_id,
        command_type=payload.command_type,
        payload=f"{payload.sensor_id};{payload.command_type};",
        status=CommandStatus.PENDING,
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return command


@router.get("/commands", response_model=Page[CommandRead], tags=["commands"])
def list_commands(
    principal: CurrentPrincipal,
    db: DbSession,
    bridge_id: str | None = Query(None),
    status_filter: CommandStatus | None = Query(None, alias="status"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    stmt = select(Command)
    if not principal.is_admin:
        stmt = stmt.where(Command.bridge_id == principal.bridge_id)
    elif bridge_id:
        stmt = stmt.where(Command.bridge_id == bridge_id)
    if status_filter is not None:
        stmt = stmt.where(Command.status == status_filter)
    stmt = (
        stmt.order_by(Command.created_at.desc(), Command.id.desc()).offset(offset).limit(limit + 1)
    )
    rows = list(db.scalars(stmt))
    has_more = len(rows) > limit
    items = rows[:limit]
    return Page(items=items, limit=limit, offset=offset, count=len(items), has_more=has_more)


@router.get("/commands/{command_id}", response_model=CommandRead, tags=["commands"])
def get_command(db: DbSession, principal: CurrentPrincipal, command_id: int = Path(ge=1)):
    command = db.get(Command, command_id)
    if command is None or (not principal.is_admin and command.bridge_id != principal.bridge_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found.")
    return command


@router.post("/commands/{command_id}/ack", response_model=CommandRead, tags=["commands"])
def acknowledge_command(db: DbSession, bridge: CurrentBridge, command_id: int = Path(ge=1)):
    command = _get_owned_command(db, command_id, bridge.bridge_id)
    if command.status != CommandStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Command already {command.status.value.lower()}.",
        )
    command.status = CommandStatus.ACKNOWLEDGED
    command.responded_at = utc_now_naive()
    db.commit()
    db.refresh(command)
    return command


@router.post("/commands/{command_id}/reject", response_model=CommandRead, tags=["commands"])
def reject_command(
    db: DbSession,
    bridge: CurrentBridge,
    command_id: int = Path(ge=1),
    payload: CommandReject | None = None,
):
    command = _get_owned_command(db, command_id, bridge.bridge_id)
    if command.status != CommandStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Command already {command.status.value.lower()}.",
        )
    command.status = CommandStatus.REJECTED
    command.responded_at = utc_now_naive()
    command.response_note = payload.note if payload is not None else None
    db.commit()
    db.refresh(command)
    return command


@router.get("/bridges", response_model=Page[BridgeRead], tags=["stations"])
def list_bridges(
    db: DbSession,
    _admin: AdminPrincipal,
    is_active: bool | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
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


@router.get("/sensors", response_model=Page[SensorRead], tags=["stations"])
def list_sensors(
    db: DbSession,
    _admin: AdminPrincipal,
    bridge_id: str | None = Query(None),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
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


api_router = router
