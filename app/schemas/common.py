"""Shared response schemas."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Offset-paginated list envelope."""

    items: list[T]
    limit: int
    offset: int
    count: int
    has_more: bool


class HealthResponse(BaseModel):
    """Liveness probe payload."""

    status: str
    version: str


class ErrorBody(BaseModel):
    """Machine-readable error detail."""

    code: str
    message: str
    details: list[dict] = []


class ErrorResponse(BaseModel):
    """Uniform error envelope returned by every failing endpoint."""

    error: ErrorBody
