"""Tests for the bridge provisioning CLI."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.security import verify_api_key
from app.db.session import SessionLocal
from app.models.bridge import Bridge
from app.scripts import create_bridge as cli

_MARKER = "API key"


def _printed_key(out: str) -> str:
    _, _, after = out.partition(_MARKER)
    return after.split(":", 1)[1].strip()


def _get(bridge_id: str) -> Bridge:
    with SessionLocal() as db:
        bridge = db.scalar(select(Bridge).where(Bridge.bridge_id == bridge_id))
    assert bridge is not None
    return bridge


def test_create_bridge_stores_only_the_hash(client, capsys):
    assert cli.main(["mostekX"]) == 0
    key = _printed_key(capsys.readouterr().out)

    bridge = _get("mostekX")
    assert bridge.is_active is True
    assert bridge.api_key_hash != key
    assert verify_api_key(key, bridge.api_key_hash)


def test_duplicate_bridge_is_refused(client, capsys):
    cli.main(["mostekY"])
    capsys.readouterr()

    with pytest.raises(SystemExit, match="already exists"):
        cli.main(["mostekY"])


def test_rotate_issues_a_new_key(client, capsys):
    cli.main(["mostekZ"])
    first = _printed_key(capsys.readouterr().out)

    assert cli.main(["mostekZ", "--rotate"]) == 0
    second = _printed_key(capsys.readouterr().out)

    assert first != second
    assert verify_api_key(second, _get("mostekZ").api_key_hash)
    assert not verify_api_key(first, _get("mostekZ").api_key_hash)


def test_deactivate_disables_bridge(client, capsys):
    cli.main(["mostekW"])
    capsys.readouterr()

    assert cli.main(["mostekW", "--deactivate"]) == 0
    assert _get("mostekW").is_active is False


def test_rotate_unknown_bridge_exits(client):
    with pytest.raises(SystemExit, match="not found"):
        cli.main(["ghost", "--rotate"])


def test_deactivate_unknown_bridge_exits(client):
    with pytest.raises(SystemExit, match="not found"):
        cli.main(["ghost", "--deactivate"])


def test_list_with_no_bridges(client, capsys):
    assert cli.main(["--list"]) == 0
    assert "No bridges registered." in capsys.readouterr().out


def test_list_reports_registered_bridges(client, capsys):
    cli.main(["mostekA"])
    capsys.readouterr()

    assert cli.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "bridge_id" in out
    assert "mostekA" in out


def test_missing_arguments_is_a_usage_error(client):
    with pytest.raises(SystemExit):
        cli.main([])
