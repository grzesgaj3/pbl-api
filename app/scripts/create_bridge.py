"""Register bridges and manage their API keys."""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.core.security import generate_api_key, hash_api_key
from app.db.session import SessionLocal
from app.models.bridge import Bridge


def _create(bridge_id: str) -> str:
    with SessionLocal() as db:
        if db.scalar(select(Bridge).where(Bridge.bridge_id == bridge_id)) is not None:
            raise SystemExit(
                f"Bridge '{bridge_id}' already exists. "
                "Use --rotate to issue a new key or --deactivate to disable it."
            )
        key = generate_api_key()
        db.add(Bridge(bridge_id=bridge_id, api_key_hash=hash_api_key(key), is_active=True))
        db.commit()
        return key


def _rotate(bridge_id: str) -> str:
    with SessionLocal() as db:
        bridge = db.scalar(select(Bridge).where(Bridge.bridge_id == bridge_id))
        if bridge is None:
            raise SystemExit(f"Bridge '{bridge_id}' not found.")
        key = generate_api_key()
        bridge.api_key_hash = hash_api_key(key)
        bridge.is_active = True
        db.commit()
        return key


def _deactivate(bridge_id: str) -> None:
    with SessionLocal() as db:
        bridge = db.scalar(select(Bridge).where(Bridge.bridge_id == bridge_id))
        if bridge is None:
            raise SystemExit(f"Bridge '{bridge_id}' not found.")
        bridge.is_active = False
        db.commit()


def _list() -> None:
    with SessionLocal() as db:
        bridges = list(db.scalars(select(Bridge).order_by(Bridge.bridge_id)))
    if not bridges:
        print("No bridges registered.")
        return
    print(f"{'bridge_id':<24} {'active':<7} created_at")
    for bridge in bridges:
        created = bridge.created_at.isoformat(sep=" ") if bridge.created_at else "-"
        print(f"{bridge.bridge_id:<24} {str(bridge.is_active):<7} {created}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.scripts.create_bridge",
        description="Provision bridge stations for the pbl API.",
    )
    parser.add_argument("bridge_id", nargs="?", help="Bridge station identifier.")
    parser.add_argument("--rotate", action="store_true", help="Issue a new key for the bridge.")
    parser.add_argument("--deactivate", action="store_true", help="Disable the bridge.")
    parser.add_argument("--list", action="store_true", help="List registered bridges.")
    args = parser.parse_args(argv)

    if args.list:
        _list()
        return 0
    if not args.bridge_id:
        parser.error("bridge_id is required (or use --list).")
    if args.rotate:
        key = _rotate(args.bridge_id)
        print(f"Rotated key for bridge '{args.bridge_id}'.\nAPI key: {key}")
        return 0
    if args.deactivate:
        _deactivate(args.bridge_id)
        print(f"Bridge '{args.bridge_id}' deactivated.")
        return 0

    key = _create(args.bridge_id)
    print(
        f"Bridge '{args.bridge_id}' created.\n"
        f"API key (store it now, it will not be shown again): {key}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
