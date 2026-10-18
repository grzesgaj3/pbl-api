"""Unit tests for the database layer that cannot be exercised over SQLite."""

from __future__ import annotations

from app.db import session as db_session


class _FakeSettings:
    database_url = "mysql+pymysql://user:pass@localhost:3306/pbl"
    db_pool_size = 2
    db_max_overflow = 3
    db_pool_recycle = 1800
    db_echo = False


class _FakeCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: str) -> None:
        self.statements.append(statement)

    def close(self) -> None:
        self.statements.append("close")


class _FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = _FakeCursor()

    def cursor(self) -> _FakeCursor:
        return self.cursor_obj


class _MysqlEngine:
    class dialect:
        name = "mysql"


class _SqliteEngine:
    class dialect:
        name = "sqlite"


def test_build_engine_configures_mysql_pool(monkeypatch):
    monkeypatch.setattr(db_session, "settings", _FakeSettings())

    engine = db_session._build_engine()
    try:
        assert engine.dialect.name == "mysql"
        assert engine.pool.size() == 2
    finally:
        engine.dispose()


def test_utc_listener_sets_time_zone_for_mysql(monkeypatch):
    monkeypatch.setattr(db_session, "engine", _MysqlEngine)
    connection = _FakeConnection()

    db_session._force_utc_session(connection, None)

    assert connection.cursor_obj.statements == ["SET time_zone = '+00:00'", "close"]


def test_utc_listener_ignores_other_dialects(monkeypatch):
    monkeypatch.setattr(db_session, "engine", _SqliteEngine)

    # Must return without touching the connection.
    db_session._force_utc_session(object(), None)


def test_get_db_closes_session():
    generator = db_session.get_db()
    session = next(generator)
    assert session is not None
    generator.close()
