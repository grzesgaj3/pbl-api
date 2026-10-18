"""Database engine, session factory and the FastAPI session dependency."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def _build_engine() -> Engine:
    """Create the SQLAlchemy engine for the configured database."""
    url = settings.database_url

    # SQLite is only used by the test-suite and for quick local smoke runs;
    # the connection arguments differ from the MySQL/MariaDB path.
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            future=True,
        )

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=settings.db_pool_recycle,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        echo=settings.db_echo,
        future=True,
    )


engine = _build_engine()


@event.listens_for(engine, "connect")
def _force_utc_session(dbapi_connection, _connection_record) -> None:
    """Force every MySQL/MariaDB session into UTC.

    ``TIMESTAMP`` columns are stored as UTC but rendered in the session time
    zone; pinning the session to ``+00:00`` keeps ``recorded_at`` consistent
    regardless of the server's default time zone.
    """
    if engine.dialect.name not in {"mysql", "mariadb"}:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("SET time_zone = '+00:00'")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
