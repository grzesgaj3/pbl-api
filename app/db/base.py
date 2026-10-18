"""Declarative base shared by all ORM models."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for ORM models.

    Alembic autogeneration and ``Base.metadata.create_all`` both rely on the
    metadata attached to this class.
    """
