"""Pydantic schemas for conversation management, requests, and responses."""

import math
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.message import MessageResponse


class ConversationCreate(BaseModel):
    """Payload schema for creating a new conversation thread."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Title or topic summary of the conversation.",
        examples=["Python Async Programming"],
    )
    system_prompt: str | None = Field(
        default=None,
        max_length=10000,
        description="Optional custom system prompt to guide LLM responses in this conversation.",
        examples=["You are an expert Python asyncio instructor."],
    )


class ConversationResponse(BaseModel):
    """Schema for returning conversation summary."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique conversation identifier.")
    title: str = Field(..., description="Conversation title.")
    system_prompt: str | None = Field(
        default=None,
        description="Custom system prompt if configured.",
    )
    created_at: datetime = Field(..., description="Conversation creation timestamp.")
    updated_at: datetime = Field(..., description="Conversation last update timestamp.")


class PaginatedConversationsResponse(BaseModel):
    """Paginated list envelope for conversations."""

    model_config = ConfigDict(extra="forbid")

    items: list[ConversationResponse] = Field(
        ...,
        description="List of conversations for the current page.",
    )
    total: int = Field(..., description="Total count of active conversations.")
    page: int = Field(..., description="Current page number.")
    page_size: int = Field(..., description="Number of items per page.")
    pages: int = Field(..., description="Total number of pages.")

    @classmethod
    def create(
        cls,
        items: list[ConversationResponse],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedConversationsResponse":
        """Compute pages count and create a paginated response object."""
        pages = math.ceil(total / page_size) if total > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


class UsageSummaryResponse(BaseModel):
    """Aggregated token usage and cost summary for a conversation."""

    model_config = ConfigDict(extra="forbid")

    total_requests: int = Field(
        default=0,
        description="Total number of LLM invocations in this conversation.",
    )
    total_tokens: int = Field(
        default=0,
        description="Total tokens consumed across all LLM requests.",
    )
    estimated_cost_usd: float = Field(
        default=0.0,
        description="Total estimated cost in USD across all LLM requests.",
    )


class ConversationDetailResponse(BaseModel):
    """Detailed conversation schema including message history and usage metrics."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique conversation identifier.")
    title: str = Field(..., description="Conversation title.")
    system_prompt: str | None = Field(
        default=None,
        description="Custom system prompt if configured.",
    )
    created_at: datetime = Field(..., description="Conversation creation timestamp.")
    updated_at: datetime = Field(..., description="Conversation last update timestamp.")
    messages: list[MessageResponse] = Field(
        default_factory=list,
        description="Chronological message history.",
    )
    usage_summary: UsageSummaryResponse = Field(
        ...,
        description="Aggregated token usage and cost summary.",
    )
