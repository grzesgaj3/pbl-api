from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    limit: int
    offset: int
    count: int
    has_more: bool


class HealthResponse(BaseModel):
    status: str
    version: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict] = []


class ErrorResponse(BaseModel):
    error: ErrorBody
