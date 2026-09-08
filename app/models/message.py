"""SQLAlchemy model for conversation messages."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.llm_request import LLMRequest

MessageRole = Literal["system", "user", "assistant"]


class Message(Base):
    """Stores individual conversation turns sequentially."""

    __tablename__ = "messages"
    __table_args__ = (
        Index(
            "idx_messages_conv_created",
            "conversation_id",
            "created_at",
            postgresql_using="btree",
        ),
    )

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
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Author role: 'system', 'user', or 'assistant'.",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Text body of the message.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )
    llm_requests: Mapped[list["LLMRequest"]] = relationship(
        "LLMRequest",
        back_populates="message",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Message(id={self.id}, conversation_id={self.conversation_id}, role='{self.role}')>"
        )
