from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "pbl-api"
    environment: str = "production"
    log_level: str = "info"
    enable_docs: bool = True

    database_url: str = Field(...)
    db_pool_size: int = Field(default=2, ge=1, le=100)
    db_max_overflow: int = Field(default=3, ge=0, le=100)
    db_pool_recycle: int = Field(default=1800, ge=-1)
    db_echo: bool = False

    admin_api_key: str = Field(..., min_length=8)

    cors_origins: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
