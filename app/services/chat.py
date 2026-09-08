"""Chat service orchestrating prompt context, retries, persistence, usage auditing, and idempotency."""

import asyncio
import time
import uuid
from decimal import Decimal

import httpx
import openai

from app.core.config import settings
from app.core.exceptions import (
    ConversationNotFoundError,
    LLMProviderError,
    LLMTimeoutError,
    ValidationError,
)
from app.core.retry import with_retry
from app.llm.base import LLMProvider
from app.llm.context import ContextManager
from app.repositories.conversation import ConversationRepository
from app.repositories.llm_request import LLMRequestRepository
from app.repositories.message import MessageRepository
from app.schemas.message import MessageResponse, MessageUsage
from app.services.cost import CostCalculatorService
from app.services.idempotency import IdempotencyService


class ChatService:
    """Service orchestrating conversational turns with LLMs, enforcing tenancy, retries, and persistence."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        message_repo: MessageRepository,
        llm_request_repo: LLMRequestRepository,
        llm_provider: LLMProvider,
        cost_calculator: CostCalculatorService,
        idempotency_service: IdempotencyService,
        context_manager: ContextManager | None = None,
    ) -> None:
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.llm_request_repo = llm_request_repo
        self.llm_provider = llm_provider
        self.cost_calculator = cost_calculator
        self.idempotency_service = idempotency_service
        self.context_manager = context_manager or ContextManager()

    async def send_message(
        self,
        conversation_id: uuid.UUID,
        api_key_id: uuid.UUID,
        content: str,
        idempotency_key: str | None = None,
    ) -> MessageResponse:
        """Process synchronous message turn, execute LLM call with retry, and record auditing metrics."""
        text = content.strip()
        if not text:
            raise ValidationError("Message content cannot be empty.")

        # 1. Check idempotency lock or cache hit
        if idempotency_key:
            cached = await self.idempotency_service.acquire_or_get(
                api_key_id=api_key_id,
                idempotency_key=idempotency_key,
            )
            if cached is not None:
                return MessageResponse.model_validate(cached)

        # 2. Check conversation existence and tenant ownership
        conversation = await self.conversation_repo.get_by_id(
            conversation_id=conversation_id,
            api_key_id=api_key_id,
            include_deleted=False,
        )
        if conversation is None:
            if idempotency_key:
                await self.idempotency_service.release_lock(api_key_id, idempotency_key)
            raise ConversationNotFoundError(f"Conversation with ID '{conversation_id}' not found.")

        # 3. Retrieve historical context and construct prompt payload
        history = await self.message_repo.list_by_conversation(conversation_id)
        context_messages = self.context_manager.build_context(
            system_prompt=conversation.system_prompt,
            history=history,
            current_prompt=text,
        )

        # 4. Persist incoming user message to database
        await self.message_repo.create(
            conversation_id=conversation_id,
            role="user",
            content=text,
        )

        start_time = time.perf_counter()

        # 5. Invoke LLM provider with transient retry handling
        try:
            llm_response = await with_retry(
                lambda: self.llm_provider.generate(messages=context_messages),
                max_attempts=settings.openai_max_retries,
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            # Record failed LLM request audit log
            await self.llm_request_repo.create(
                conversation_id=conversation_id,
                message_id=None,
                model=getattr(self.llm_provider, "default_model", settings.openai_model),
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                estimated_cost=Decimal("0.000000"),
                latency_ms=elapsed_ms,
                status="error",
                error_message=str(exc),
            )

            # Release idempotency lock on failure so caller can retry
            if idempotency_key:
                await self.idempotency_service.release_lock(api_key_id, idempotency_key)

            if isinstance(
                exc,
                (
                    TimeoutError,
                    asyncio.TimeoutError,
                    openai.APITimeoutError,
                    httpx.TimeoutException,
                ),
            ):
                raise LLMTimeoutError("Upstream LLM provider request timed out.") from exc

            raise LLMProviderError(f"Upstream LLM provider error: {str(exc)}") from exc

        # 6. Persist generated assistant response message
        assistant_msg = await self.message_repo.create(
            conversation_id=conversation_id,
            role="assistant",
            content=llm_response.content,
        )

        # 7. Calculate cost and record successful LLM audit log
        cost = self.cost_calculator.calculate_cost(
            model=llm_response.model,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
        )

        await self.llm_request_repo.create(
            conversation_id=conversation_id,
            message_id=assistant_msg.id,
            model=llm_response.model,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            total_tokens=llm_response.total_tokens,
            estimated_cost=cost,
            latency_ms=llm_response.latency_ms,
            status="success",
        )

        # 8. Build response model
        usage = MessageUsage(
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            total_tokens=llm_response.total_tokens,
            estimated_cost_usd=float(cost),
            latency_ms=llm_response.latency_ms,
        )

        response = MessageResponse(
            id=assistant_msg.id,
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_msg.content,
            created_at=assistant_msg.created_at,
            usage=usage,
        )

        # 9. Cache successful response in Redis for idempotency
        if idempotency_key:
            await self.idempotency_service.store_response(
                api_key_id=api_key_id,
                idempotency_key=idempotency_key,
                response=response.model_dump(mode="json"),
            )

        return response
