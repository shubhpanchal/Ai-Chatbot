"""SQLAlchemy model for LLM request auditing, tokens, latency, and costs."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message import Message

LLMRequestStatus = Literal["success", "error", "cancelled"]


class LLMRequest(Base):
    """Audit log of every external LLM interaction, token usage, latency, and cost calculation."""

    __tablename__ = "llm_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Reference to generated assistant message, if persisted.",
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Name of the model invoked (e.g. gpt-4o-mini).",
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of input prompt tokens processed.",
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of output completion tokens generated.",
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Total tokens consumed.",
    )
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
        default=Decimal("0.000000"),
        doc="Calculated cost of this request in USD.",
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Total request duration in milliseconds.",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="success",
        doc="Execution outcome: 'success', 'error', or 'cancelled'.",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Error message or exception details if request failed.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="llm_requests",
    )
    message: Mapped["Message | None"] = relationship(
        "Message",
        back_populates="llm_requests",
    )

    def __repr__(self) -> str:
        return (
            f"<LLMRequest(id={self.id}, model='{self.model}', tokens={self.total_tokens}, "
            f"cost=${self.estimated_cost}, status='{self.status}')>"
        )
