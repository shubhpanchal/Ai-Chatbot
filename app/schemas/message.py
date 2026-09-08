"""Pydantic schemas for conversation messages."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageResponse(BaseModel):
    """Schema for returning message records."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique message identifier.")
    role: str = Field(..., description="Message author role: 'system', 'user', or 'assistant'.")
    content: str = Field(..., description="Text body of the message.")
    created_at: datetime = Field(..., description="Message creation timestamp.")
