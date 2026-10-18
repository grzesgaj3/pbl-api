"""Integration tests against a real MariaDB/MySQL instance.

Skipped unless ``PBL_TEST_MYSQL_URL`` is set, because the point of these tests
is to exercise what SQLite cannot: native ``ENUM``, ``BIGINT`` auto-increment,
``DEFAULT CURRENT_TIMESTAMP`` and the ``utf8mb4`` table options.

    PBL_TEST_MYSQL_URL='mysql+pymysql://root@127.0.0.1:3306/pbl_test' \
        pytest -m integration
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_api_key
from app.db.base import Base
from app.models import Bridge, Command, CommandStatus, Measurement

MYSQL_URL = os.environ.get("PBL_TEST_MYSQL_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not MYSQL_URL, reason="set PBL_TEST_MYSQL_URL to run"),
]


@pytest.fixture(scope="module")
def mariadb():
    engine = create_engine(MYSQL_URL, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_tables_use_utf8mb4(mariadb):
    with mariadb.connect() as connection:
        charset = connection.execute(
            text(
                "SELECT table_collation FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'measurements'"
            )
        ).scalar_one()
    assert charset.startswith("utf8mb4")


def test_measurement_roundtrip_and_idempotency(mariadb):
    sent_at = datetime(2024, 10, 18, 14, 0, 0)
    with Session(mariadb) as db:
        db.add(Bridge(bridge_id="mostek1", api_key_hash=hash_api_key("k"), is_active=True))
        db.commit()

        measurement = Measurement(
            bridge_id="mostek1",
            sensor_id="sensor1",
            value_mm=Decimal("3.40"),
            sent_at=sent_at,
        )
        db.add(measurement)
        db.commit()
        db.refresh(measurement)

        # recorded_at must be filled in by the database, not by Python.
        assert measurement.recorded_at is not None
        assert measurement.id > 0

        db.add(
            Measurement(
                bridge_id="mostek1",
                sensor_id="sensor1",
                value_mm=Decimal("1.00"),
                sent_at=sent_at,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_command_status_is_a_native_enum(mariadb):
    with Session(mariadb) as db:
        bridge = db.scalar(select(Bridge).where(Bridge.bridge_id == "mostek1"))
        if bridge is None:
            db.add(Bridge(bridge_id="mostek1", api_key_hash=hash_api_key("k")))
            db.commit()

        command = Command(
            bridge_id="mostek1",
            sensor_id="sensor1",
            command_type="clean",
            payload="sensor1;clean;",
            status=CommandStatus.PENDING,
        )
        db.add(command)
        db.commit()
        db.refresh(command)

        stored = db.get(Command, command.id)
        assert stored.status is CommandStatus.PENDING

    with mariadb.connect() as connection:
        column_type = connection.execute(
            text(
                "SELECT column_type FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'commands' "
                "AND column_name = 'status'"
            )
        ).scalar_one()
    assert column_type.lower().startswith("enum(")
