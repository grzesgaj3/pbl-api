"""Application factory and ASGI entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, status
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


def _error_response(status_code, message, details=None, headers=None):
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
    async def _http(_request, exc: StarletteHTTPException):
        return _error_response(exc.status_code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_request, exc: RequestValidationError):
        details = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        return _error_response(422, "Request validation failed.", details)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
        openapi_tags=[
            {"name": "measurements", "description": "Rainfall readings."},
            {"name": "commands", "description": "Rain-gauge cleaning commands."},
            {"name": "stations", "description": "Registered bridge and sensor stations (admin)."},
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

    @app.get("/health", response_model=HealthResponse, tags=["ops"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @app.get("/health/ready", response_model=HealthResponse, tags=["ops"])
    def health_ready() -> HealthResponse:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            logging.getLogger(__name__).warning("Readiness probe failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable."
            ) from exc
        return HealthResponse(status="ok", version=__version__)

    return app


app = create_app()
