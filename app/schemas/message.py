"""Pydantic schemas for conversation messages and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    """Payload schema for sending a new message in a conversation."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="Text content of the user message.",
        examples=["Explain Python asyncio tasks in simple terms."],
    )


class MessageUsage(BaseModel):
    """Token accounting and latency metrics for an assistant message response."""

    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = Field(..., description="Number of prompt tokens processed.")
    completion_tokens: int = Field(..., description="Number of completion tokens generated.")
    total_tokens: int = Field(..., description="Total tokens consumed.")
    estimated_cost_usd: float = Field(..., description="Calculated cost of this turn in USD.")
    latency_ms: int = Field(..., description="LLM execution duration in milliseconds.")


class MessageResponse(BaseModel):
    """Schema for returning message records and generated assistant responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique message identifier.")
    conversation_id: uuid.UUID | None = Field(
        default=None,
        description="ID of the conversation thread.",
    )
    role: str = Field(..., description="Author role: 'system', 'user', or 'assistant'.")
    content: str = Field(..., description="Text body of the message.")
    created_at: datetime = Field(..., description="Message creation timestamp.")
    usage: MessageUsage | None = Field(
        default=None,
        description="Token accounting and cost metrics (included on generation responses).",
    )


class StreamTokenEvent(BaseModel):
    """Schema for incremental token SSE events."""

    token: str = Field(..., description="Incremental token text.")
    index: int = Field(..., description="Zero-based token sequence index.")


class StreamDoneEvent(BaseModel):
    """Schema for final completion SSE event."""

    message_id: uuid.UUID = Field(..., description="Persisted assistant message ID.")
    total_tokens: int = Field(..., description="Total tokens consumed in this turn.")
    estimated_cost_usd: float = Field(..., description="Estimated cost of this turn in USD.")
    finish_reason: str = Field(default="stop", description="Model completion reason.")
