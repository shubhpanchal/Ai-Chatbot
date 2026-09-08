"""Repository for LLM execution audit records and token tracking."""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_request import LLMRequest
from app.repositories.base import BaseRepository


class LLMRequestRepository(BaseRepository[LLMRequest]):
    """Data access layer for LLM audit records."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LLMRequest)

    async def create(
        self,
        conversation_id: uuid.UUID,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        estimated_cost: Decimal,
        latency_ms: int,
        status: str,
        message_id: uuid.UUID | None = None,
        error_message: str | None = None,
    ) -> LLMRequest:
        """Create and persist an immutable LLM request audit record."""
        record = LLMRequest(
            conversation_id=conversation_id,
            message_id=message_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[LLMRequest]:
        """Fetch all LLM audit logs for a conversation ordered chronologically."""
        stmt = (
            select(LLMRequest)
            .where(LLMRequest.conversation_id == conversation_id)
            .order_by(LLMRequest.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
