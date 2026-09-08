"""Repository for conversation persistence, pagination, and tenant isolation."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.llm_request import LLMRequest
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """Data access layer for conversation entities with tenant isolation."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Conversation)

    async def create(
        self,
        api_key_id: uuid.UUID,
        title: str,
        system_prompt: str | None = None,
    ) -> Conversation:
        """Create and persist a new conversation owned by the designated API key."""
        conversation = Conversation(
            api_key_id=api_key_id,
            title=title,
            system_prompt=system_prompt,
        )
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def get_by_id(
        self,
        conversation_id: uuid.UUID,
        api_key_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> Conversation | None:
        """Fetch a conversation by ID, strictly enforcing tenant ownership and soft-delete filters."""
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.api_key_id == api_key_id,
        )
        if not include_deleted:
            stmt = stmt.where(Conversation.deleted_at.is_(None))

        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_api_key(
        self,
        api_key_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Conversation], int]:
        """List active conversations owned by the caller with pagination."""
        offset = (page - 1) * page_size

        # Total count query
        count_stmt = select(func.count(Conversation.id)).where(
            Conversation.api_key_id == api_key_id,
            Conversation.deleted_at.is_(None),
        )
        total_result = await self.session.execute(count_stmt)
        total: int = total_result.scalar() or 0

        # Items query ordered by created_at DESC
        items_stmt = (
            select(Conversation)
            .where(
                Conversation.api_key_id == api_key_id,
                Conversation.deleted_at.is_(None),
            )
            .order_by(Conversation.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items_result = await self.session.execute(items_stmt)
        items = list(items_result.scalars().all())

        return items, total

    async def soft_delete(
        self,
        conversation_id: uuid.UUID,
        api_key_id: uuid.UUID,
    ) -> bool:
        """Soft delete an active conversation. Returns True if deleted, False if not found/already deleted."""
        stmt = (
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.api_key_id == api_key_id,
                Conversation.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        if isinstance(result, CursorResult):
            return result.rowcount > 0
        return False

    async def get_usage_stats(self, conversation_id: uuid.UUID) -> dict[str, Any]:
        """Aggregate total token usage and cost for a conversation from llm_requests."""
        stmt = select(
            func.count(LLMRequest.id).label("total_requests"),
            func.coalesce(func.sum(LLMRequest.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(LLMRequest.estimated_cost), Decimal("0.000000")).label(
                "estimated_cost_usd"
            ),
        ).where(LLMRequest.conversation_id == conversation_id)

        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "total_requests": int(row.total_requests),
            "total_tokens": int(row.total_tokens),
            "estimated_cost_usd": float(row.estimated_cost_usd),
        }
