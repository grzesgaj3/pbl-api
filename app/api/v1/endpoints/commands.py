"""Cleaning-command endpoints.

Flow: the admin creates a command for one sensor behind a bridge; the bridge
polls for pending commands, forwards the generated LoRa payload and finally
acknowledges or rejects the command.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy import select

from app.api.deps import AdminPrincipal, CurrentBridge, CurrentPrincipal, DbSession
from app.core.payloads import build_command_payload
from app.core.timeutil import utc_now_naive
from app.models.bridge import Bridge
from app.models.command import Command, CommandStatus
from app.schemas.command import CommandCreate, CommandRead, CommandReject
from app.schemas.common import ErrorResponse, Page

router = APIRouter(prefix="/commands", tags=["commands"])

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


def _get_owned_command(db: DbSession, command_id: int, bridge_id: str) -> Command:
    """Fetch a command, hiding existence from other bridges."""
    command = db.get(Command, command_id)
    if command is None or command.bridge_id != bridge_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found.")
    return command


@router.post(
    "",
    response_model=CommandRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a rain-gauge cleaning command (admin)",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Unknown bridge."},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Admin key required."},
    },
)
def create_command(payload: CommandCreate, db: DbSession, _admin: AdminPrincipal) -> Command:
    """Queue a cleaning command for a bridge; the LoRa payload is generated here."""
    bridge = db.scalar(select(Bridge).where(Bridge.bridge_id == payload.bridge_id))
    if bridge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bridge '{payload.bridge_id}' not found.",
        )

    command = Command(
        bridge_id=payload.bridge_id,
        sensor_id=payload.sensor_id,
        command_type=payload.command_type,
        payload=build_command_payload(payload.sensor_id, payload.command_type),
        status=CommandStatus.PENDING,
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return command


@router.get(
    "",
    response_model=Page[CommandRead],
    summary="List commands",
    description="A bridge sees only its own commands; the admin sees all of them.",
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
def list_commands(
    principal: CurrentPrincipal,
    db: DbSession,
    bridge_id: str | None = Query(None, description="Filter by bridge (admin only)."),
    status_filter: CommandStatus | None = Query(
        None, alias="status", description="Filter by status, e.g. PENDING."
    ),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
) -> Page[CommandRead]:
    """Return queued commands, newest first."""
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


@router.get(
    "/{command_id}",
    response_model=CommandRead,
    summary="Get a single command",
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
def get_command(
    db: DbSession,
    principal: CurrentPrincipal,
    command_id: int = Path(ge=1),
) -> Command:
    """Return one command the caller is allowed to see."""
    command = db.get(Command, command_id)
    if command is None or (not principal.is_admin and command.bridge_id != principal.bridge_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found.")
    return command


@router.post(
    "/{command_id}/ack",
    response_model=CommandRead,
    summary="Acknowledge a command (bridge)",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "Already answered."},
    },
)
def acknowledge_command(
    db: DbSession,
    bridge: CurrentBridge,
    command_id: int = Path(ge=1),
) -> Command:
    """Mark a command as read; the bridge will send it to the field network."""
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


@router.post(
    "/{command_id}/reject",
    response_model=CommandRead,
    summary="Reject a command (bridge)",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "Already answered."},
    },
)
def reject_command(
    payload: CommandReject,
    db: DbSession,
    bridge: CurrentBridge,
    command_id: int = Path(ge=1),
) -> Command:
    """Mark a command as rejected, optionally recording why."""
    command = _get_owned_command(db, command_id, bridge.bridge_id)
    if command.status != CommandStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Command already {command.status.value.lower()}.",
        )

    command.status = CommandStatus.REJECTED
    command.responded_at = utc_now_naive()
    command.response_note = payload.note
    db.commit()
    db.refresh(command)
    return command
