"""Application factory and ASGI entrypoint.

Run with::

    uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.db.session import engine
from app.schemas.common import HealthResponse

logger = logging.getLogger(__name__)

_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
}

_DESCRIPTION = """
API for storing rainfall measurements reported by LoRa rain gauges and for
queueing rain-gauge cleaning commands.

**Authentication** — every endpoint except the health checks requires an
`X-API-Key` header:

* a **bridge key** (per bridge station) — store measurements, read own
  measurements, poll and answer own cleaning commands;
* the **admin key** (`ADMIN_API_KEY`) — create cleaning commands and read data
  from every bridge.
"""


def _error_response(
    status_code: int, message: str, details: list[dict] | None = None, headers: dict | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": _ERROR_CODES.get(status_code, "http_error"),
                "message": message,
                "details": jsonable_encoder(details or []),
            }
        },
        headers=headers,
    )


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(_request: Request, exc: StarletteHTTPException):
        return _error_response(exc.status_code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(_request: Request, exc: RequestValidationError):
        details = [
            {"loc": list(error.get("loc", [])), "msg": error.get("msg"), "type": error.get("type")}
            for error in exc.errors()
        ]
        return _error_response(422, "Request validation failed.", details)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()

    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=_DESCRIPTION,
        openapi_tags=[
            {"name": "measurements", "description": "Rainfall readings."},
            {"name": "commands", "description": "Rain-gauge cleaning commands."},
            {"name": "ops", "description": "Health checks."},
        ],
    )

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST"],
            allow_headers=["X-API-Key", "Content-Type"],
        )

    _register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", response_model=HealthResponse, tags=["ops"], summary="Liveness probe")
    def health() -> HealthResponse:
        """Cheap liveness check that does not touch the database."""
        return HealthResponse(status="ok", version=__version__)

    @app.get(
        "/health/ready",
        response_model=HealthResponse,
        tags=["ops"],
        summary="Readiness probe",
    )
    def health_ready() -> HealthResponse:
        """Readiness check: verifies the database is reachable."""
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:  # pragma: no cover - depends on environment
            logger.warning("Readiness probe failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable.",
            ) from exc
        return HealthResponse(status="ok", version=__version__)

    return app


app = create_app()
