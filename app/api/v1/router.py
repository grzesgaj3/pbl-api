"""Aggregated API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import commands, measurements

api_router = APIRouter()
api_router.include_router(measurements.router)
api_router.include_router(commands.router)
