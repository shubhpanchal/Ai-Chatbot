"""Health, readiness, and observability probe routes."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis
from app.core.config import settings
from app.core.metrics import metrics
from app.schemas.health import HealthResponse, ReadinessResponse

if TYPE_CHECKING:
    RedisClient = Redis[str]
else:
    RedisClient = Redis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness Probe",
    description="Returns liveness status of the API process without pinging external dependencies.",
)
async def get_health() -> HealthResponse:
    """Return application liveness status."""
    return HealthResponse(status="healthy")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
    description="Verifies connectivity to critical dependencies (PostgreSQL, Redis).",
    responses={
        200: {"description": "Service is ready to receive traffic."},
        503: {"description": "One or more critical dependencies are unreachable."},
    },
)
async def get_readiness(
    response: Response,
    session: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
) -> ReadinessResponse:
    """Execute readiness health checks on PostgreSQL and Redis dependencies."""
    checks: dict[str, str] = {}
    is_ready = True

    # 1. PostgreSQL Database Connectivity Check
    try:
        await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=2.0)
        checks["database"] = "connected"
    except Exception as exc:
        logger.error("Readiness check: PostgreSQL unreachable: %s", exc)
        checks["database"] = "unreachable"
        is_ready = False

    # 2. Redis Cache & Rate Limiter Check
    try:
        await asyncio.wait_for(redis.ping(), timeout=2.0)
        checks["redis"] = "connected"
    except Exception as exc:
        logger.error("Readiness check: Redis unreachable: %s", exc)
        checks["redis"] = "unreachable"
        is_ready = False

    # 3. LLM Configuration Check
    if settings.llm_provider.lower() == "mock" or bool(settings.openai_api_key):
        checks["llm_config"] = "valid"
    else:
        checks["llm_config"] = "missing_api_key"
        is_ready = False

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="unready", checks=checks)

    return ReadinessResponse(status="ready", checks=checks)


@router.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    summary="Metrics Snapshot",
    description="Returns an aggregated JSON snapshot of in-memory application and infrastructure metrics.",
)
async def get_metrics() -> dict[str, Any]:
    """Return current metrics registry snapshot."""
    return metrics.get_snapshot()
