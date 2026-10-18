"""Declarative base shared by all ORM models."""

from __future__ import annotations

from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for ORM models.

    Alembic autogeneration and ``Base.metadata.create_all`` both rely on the
    metadata attached to this class.
    """


# Primary-key type: INTEGER on SQLite (which only auto-increments a literal
# "INTEGER PRIMARY KEY", as used by the test-suite) and BIGINT on MariaDB/MySQL
# via the dialect variant.
PRIMARY_KEY_TYPE = Integer().with_variant(BigInteger, "mysql")
