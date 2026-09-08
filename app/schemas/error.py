"""Standard error response schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Detailed error object returned inside standard error responses."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Standardized application error code.")
    message: str = Field(..., description="Human-readable explanation of the error.")
    request_id: str | None = Field(
        default=None,
        description="Unique request tracing identifier.",
    )
    details: Any = Field(
        default=None,
        description="Optional structured diagnostic details or validation errors.",
    )


class ErrorResponse(BaseModel):
    """Top-level standard error response envelope."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail
