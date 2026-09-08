"""Health check and readiness schema models."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema for liveness probe response."""

    status: Literal["healthy"] = Field(
        default="healthy",
        description="Liveness status of the application process.",
        examples=["healthy"],
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Current server timestamp in UTC.",
    )


class ReadinessResponse(BaseModel):
    """Schema for readiness probe response checking critical dependencies."""

    status: Literal["ready", "unready"] = Field(
        description="Readiness status of the application dependencies.",
        examples=["ready", "unready"],
    )
    checks: dict[str, str] = Field(
        description="Status of individual critical dependencies (database, redis, llm_config).",
        examples=[{"database": "connected", "redis": "connected", "llm_config": "valid"}],
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Current server timestamp in UTC.",
    )
