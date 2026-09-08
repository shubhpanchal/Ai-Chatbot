"""SQLAlchemy model for conversation threads."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.api_key import APIKey
    from app.models.llm_request import LLMRequest
    from app.models.message import Message


class Conversation(Base):
    """Stores conversation thread metadata and tenant ownership."""

    __tablename__ = "conversations"
    __table_args__ = (
        Index(
            "idx_conversations_api_key_created",
            "api_key_id",
            "created_at",
            postgresql_using="btree",
        ),
        Index(
            "idx_conversations_api_key_deleted",
            "api_key_id",
            "deleted_at",
            postgresql_using="btree",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant owner foreign key.",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Title or topic summary of the conversation.",
    )
    system_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Conversation-specific custom system instruction.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Soft deletion timestamp. If not null, logically deleted.",
    )

    # Relationships
    api_key: Mapped["APIKey"] = relationship(
        "APIKey",
        back_populates="conversations",
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
        lazy="selectin",
    )
    llm_requests: Mapped[list["LLMRequest"]] = relationship(
        "LLMRequest",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def is_deleted(self) -> bool:
        """Check if conversation has been soft deleted."""
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, title='{self.title}', api_key_id={self.api_key_id})>"
