"""Repository for message persistence and chronological context retrieval."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """Data access layer for conversation messages."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Message)

    async def create(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
    ) -> Message:
        """Create and persist a new conversation message."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def list_by_conversation(
        self,
        conversation_id: uuid.UUID,
    ) -> list[Message]:
        """Fetch all messages in a conversation ordered chronologically by created_at ASC."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_conversation(self, conversation_id: uuid.UUID) -> int:
        """Count total messages belonging to a conversation."""
        stmt = select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
        result = await self.session.execute(stmt)
        total: int = result.scalar() or 0
        return total
