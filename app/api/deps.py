"""FastAPI dependencies: database session, authentication and authorisation.

Two credentials exist:

* a per-bridge API key (``X-API-Key``), stored only as a SHA-256 hash, and
* a single admin key from configuration.

Endpoints choose one of three dependencies: :data:`CurrentBridge` (bridge
only), :data:`AdminOnly` (admin only) or :data:`CurrentPrincipal` (either).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_api_key, verify_admin_key
from app.core.timeutil import utc_now_naive
from app.db.session import get_db
from app.models.bridge import Bridge

# Only refresh last_seen_at at most this often, to avoid a write per request.
LAST_SEEN_REFRESH = timedelta(hours=1)

DbSession = Annotated[Session, Depends(get_db)]

ApiKeyHeader = Annotated[
    str | None,
    Header(alias="X-API-Key", description="Bridge or admin API key."),
]


@dataclass(frozen=True)
class Principal:
    """The authenticated caller of a request."""

    is_admin: bool
    bridge: Bridge | None

    @property
    def bridge_id(self) -> str | None:
        return self.bridge.bridge_id if self.bridge is not None else None


def _missing_key_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing X-API-Key header.",
        headers={"WWW-Authenticate": "ApiKey"},
    )


def _forbidden_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid or inactive API key.",
    )


def _lookup_bridge(db: Session, api_key: str) -> Bridge | None:
    digest = hash_api_key(api_key)
    return db.scalar(
        select(Bridge).where(Bridge.api_key_hash == digest, Bridge.is_active.is_(True))
    )


def _touch_bridge(db: Session, bridge: Bridge) -> None:
    """Record that the bridge was seen, at most once per interval."""
    now = utc_now_naive()
    if bridge.last_seen_at is None or now - bridge.last_seen_at >= LAST_SEEN_REFRESH:
        bridge.last_seen_at = now
        db.commit()


def require_principal(db: DbSession, x_api_key: ApiKeyHeader = None) -> Principal:
    """Authenticate the caller as either an admin or a bridge."""
    if not x_api_key:
        raise _missing_key_exception()

    if verify_admin_key(x_api_key, get_settings().admin_api_key):
        return Principal(is_admin=True, bridge=None)

    bridge = _lookup_bridge(db, x_api_key)
    if bridge is None:
        raise _forbidden_exception()

    _touch_bridge(db, bridge)
    return Principal(is_admin=False, bridge=bridge)


def require_admin(db: DbSession, x_api_key: ApiKeyHeader = None) -> Principal:
    """Authenticate the caller as the admin."""
    if not x_api_key:
        raise _missing_key_exception()

    if not verify_admin_key(x_api_key, get_settings().admin_api_key):
        raise _forbidden_exception()

    return Principal(is_admin=True, bridge=None)


def require_bridge(db: DbSession, x_api_key: ApiKeyHeader = None) -> Bridge:
    """Authenticate the caller as an active bridge and return it."""
    if not x_api_key:
        raise _missing_key_exception()

    bridge = _lookup_bridge(db, x_api_key)
    if bridge is None:
        raise _forbidden_exception()

    _touch_bridge(db, bridge)
    return bridge


CurrentPrincipal = Annotated[Principal, Depends(require_principal)]
AdminPrincipal = Annotated[Principal, Depends(require_admin)]
CurrentBridge = Annotated[Bridge, Depends(require_bridge)]
