"""Health check schema models."""

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
