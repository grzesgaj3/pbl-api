"""Typed application configuration.

Settings are read from environment variables and, when present, from a
``.env`` file in the project root. Loading is cached so the file is parsed
once per process.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for the API."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ------------------------------------------------------
    app_name: str = "pbl-api"
    environment: str = "production"
    log_level: str = "info"
    enable_docs: bool = Field(
        default=True,
        description="Serve /docs, /redoc and /openapi.json. Disable in production if not needed.",
    )

    # --- Database ---------------------------------------------------------
    database_url: str = Field(
        ...,
        description="SQLAlchemy URL, e.g. mysql+pymysql://user:pass@host:3306/db",
    )
    db_pool_size: int = Field(default=2, ge=1, le=100)
    db_max_overflow: int = Field(default=3, ge=0, le=100)
    db_pool_recycle: int = Field(default=1800, ge=-1)
    db_echo: bool = False

    # --- Security ---------------------------------------------------------
    admin_api_key: str = Field(
        ...,
        min_length=8,
        description="Key authorising admin endpoints (command creation, full reads).",
    )

    # --- HTTP -------------------------------------------------------------
    cors_origins: str = Field(
        default="",
        description="Comma-separated allowed CORS origins. Empty disables CORS.",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Return configured CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached)."""
    return Settings()
