"""Chat service orchestrating prompt context, retries, persistence, usage auditing, and idempotency."""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from decimal import Decimal
from typing import Any

import httpx
import openai

from app.core.config import settings
from app.core.exceptions import (
    ConversationNotFoundError,
    LLMProviderError,
    LLMTimeoutError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.metrics import metrics
from app.core.retry import with_retry
from app.llm.base import LLMMessage, LLMProvider
from app.llm.context import ContextManager
from app.models.conversation import Conversation
from app.repositories.conversation import ConversationRepository
from app.repositories.llm_request import LLMRequestRepository
from app.repositories.message import MessageRepository
from app.schemas.message import (
    MessageResponse,
    MessageUsage,
    StreamDoneEvent,
    StreamTokenEvent,
)
from app.services.cost import CostCalculatorService
from app.services.idempotency import IdempotencyService

logger = get_logger(__name__)


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
                metrics.record_idempotency_hit()
                logger.info(
                    "idempotency_cache_hit",
                    conversation_id=str(conversation_id),
                )
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
        model_name = getattr(self.llm_provider, "default_model", settings.openai_model)
        logger.info(
            "llm_generation_started",
            conversation_id=str(conversation_id),
            context_messages_count=len(context_messages),
            model=model_name,
        )

        # 5. Invoke LLM provider with transient retry handling
        try:
            llm_response = await with_retry(
                lambda: self.llm_provider.generate(messages=context_messages),
                max_attempts=settings.openai_max_retries,
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            # Record failed LLM request audit log and metric
            metrics.record_llm_request(
                provider=settings.llm_provider,
                model=model_name,
                status="error",
                duration_ms=elapsed_ms,
            )
            logger.error(
                "llm_generation_failed",
                conversation_id=str(conversation_id),
                model=model_name,
                latency_ms=elapsed_ms,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

            await self.llm_request_repo.create(
                conversation_id=conversation_id,
                message_id=None,
                model=model_name,
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

        # 7. Calculate cost and record successful LLM audit log and metrics
        cost = self.cost_calculator.calculate_cost(
            model=llm_response.model,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
        )

        metrics.record_llm_request(
            provider=settings.llm_provider,
            model=llm_response.model,
            status="success",
            duration_ms=llm_response.latency_ms,
        )
        metrics.record_tokens(
            provider=settings.llm_provider,
            model=llm_response.model,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
        )
        metrics.record_cost(
            provider=settings.llm_provider,
            model=llm_response.model,
            cost_usd=float(cost),
        )
        metrics.record_conversation_op("send_message")

        logger.info(
            "llm_generation_completed",
            conversation_id=str(conversation_id),
            model=llm_response.model,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            total_tokens=llm_response.total_tokens,
            latency_ms=llm_response.latency_ms,
            estimated_cost_usd=float(cost),
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

    async def prepare_stream_turn(
        self,
        conversation_id: uuid.UUID,
        api_key_id: uuid.UUID,
        content: str,
        idempotency_key: str | None = None,
    ) -> tuple[Conversation | None, list[LLMMessage], dict[str, Any] | None]:
        """Validate ownership, check idempotency, persist user message, and build prompt context before streaming begins."""
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
                return None, [], cached

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

        return conversation, context_messages, None

    async def stream_message(
        self,
        conversation_id: uuid.UUID,
        api_key_id: uuid.UUID,
        context_messages: list[LLMMessage],
        cached_response: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        is_disconnected: Callable[[], Awaitable[bool]] | None = None,
    ) -> AsyncIterator[str]:
        """Stream assistant tokens as SSE events with disconnect cancellation and post-stream persistence."""
        # 1. Idempotency replay branch: stream cached assistant turn
        if cached_response is not None:
            metrics.record_idempotency_hit()
            logger.info("idempotency_cache_hit_streaming", conversation_id=str(conversation_id))
            cached_content = str(cached_response.get("content", ""))
            token_event = StreamTokenEvent(token=cached_content, index=0)
            yield f"event: token\ndata: {token_event.model_dump_json()}\n\n"

            msg_id = uuid.UUID(str(cached_response["id"]))
            cached_usage = cached_response.get("usage") or {}
            done_event = StreamDoneEvent(
                message_id=msg_id,
                total_tokens=int(cached_usage.get("total_tokens", 0)),
                estimated_cost_usd=float(cached_usage.get("estimated_cost_usd", 0.0)),
                finish_reason="stop",
            )
            yield f"event: done\ndata: {done_event.model_dump_json()}\n\n"
            return

        # 2. Live streaming execution
        start_time = time.perf_counter()
        ttft_ms: int | None = None
        accumulated_tokens: list[str] = []
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        total_tokens: int | None = None
        finish_reason = "stop"
        model_name = getattr(self.llm_provider, "default_model", settings.openai_model)
        logger.info("llm_stream_started", conversation_id=str(conversation_id), model=model_name)
        stream_iter = self.llm_provider.generate_stream(messages=context_messages)
        cancelled = False

        try:
            async for chunk in stream_iter:
                # Check client disconnection before flushing token
                if is_disconnected and await is_disconnected():
                    cancelled = True
                    break

                if chunk.delta:
                    if ttft_ms is None:
                        ttft_ms = int((time.perf_counter() - start_time) * 1000)
                        metrics.record_stream_ttft(
                            provider=settings.llm_provider,
                            model=model_name,
                            ttft_ms=float(ttft_ms),
                        )
                        logger.info(
                            "llm_stream_first_token",
                            conversation_id=str(conversation_id),
                            ttft_ms=ttft_ms,
                            model=model_name,
                        )
                    accumulated_tokens.append(chunk.delta)
                    token_event = StreamTokenEvent(token=chunk.delta, index=chunk.index)
                    yield f"event: token\ndata: {token_event.model_dump_json()}\n\n"

                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason
                if chunk.prompt_tokens is not None:
                    prompt_tokens = chunk.prompt_tokens
                if chunk.completion_tokens is not None:
                    completion_tokens = chunk.completion_tokens
                if chunk.total_tokens is not None:
                    total_tokens = chunk.total_tokens

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            # 3. Handle client disconnection mid-stream
            if cancelled:
                metrics.record_streaming_cancellation()
                metrics.record_llm_request(
                    provider=settings.llm_provider,
                    model=model_name,
                    status="cancelled",
                    duration_ms=elapsed_ms,
                )
                logger.warning(
                    "llm_stream_client_disconnected",
                    conversation_id=str(conversation_id),
                    latency_ms=elapsed_ms,
                    tokens_streamed=len(accumulated_tokens),
                    model=model_name,
                )

                calc_prompt_tokens = (
                    prompt_tokens if prompt_tokens is not None else len(context_messages) * 10
                )
                calc_comp_tokens = (
                    completion_tokens if completion_tokens is not None else len(accumulated_tokens)
                )
                cost = self.cost_calculator.calculate_cost(
                    model=model_name,
                    prompt_tokens=calc_prompt_tokens,
                    completion_tokens=calc_comp_tokens,
                )

                # Persist cancelled audit record (DO NOT save partial assistant message)
                await self.llm_request_repo.create(
                    conversation_id=conversation_id,
                    message_id=None,
                    model=model_name,
                    prompt_tokens=calc_prompt_tokens,
                    completion_tokens=calc_comp_tokens,
                    total_tokens=calc_prompt_tokens + calc_comp_tokens,
                    estimated_cost=cost,
                    latency_ms=elapsed_ms,
                    status="cancelled",
                    error_message="Client disconnected during streaming.",
                )

                if idempotency_key:
                    await self.idempotency_service.release_lock(api_key_id, idempotency_key)
                return

            # 4. Successful completion: Persist complete assistant message
            full_content = "".join(accumulated_tokens)
            assistant_msg = await self.message_repo.create(
                conversation_id=conversation_id,
                role="assistant",
                content=full_content,
            )

            calc_prompt_tokens = (
                prompt_tokens if prompt_tokens is not None else len(context_messages) * 10
            )
            calc_comp_tokens = (
                completion_tokens
                if completion_tokens is not None
                else max(1, len(full_content.split())) * 2
            )
            calc_total_tokens = (
                total_tokens
                if total_tokens is not None
                else (calc_prompt_tokens + calc_comp_tokens)
            )

            cost = self.cost_calculator.calculate_cost(
                model=model_name,
                prompt_tokens=calc_prompt_tokens,
                completion_tokens=calc_comp_tokens,
            )

            metrics.record_llm_request(
                provider=settings.llm_provider,
                model=model_name,
                status="success",
                duration_ms=elapsed_ms,
            )
            metrics.record_tokens(
                provider=settings.llm_provider,
                model=model_name,
                prompt_tokens=calc_prompt_tokens,
                completion_tokens=calc_comp_tokens,
            )
            metrics.record_cost(
                provider=settings.llm_provider,
                model=model_name,
                cost_usd=float(cost),
            )
            metrics.record_conversation_op("stream_message")

            logger.info(
                "llm_stream_completed",
                conversation_id=str(conversation_id),
                model=model_name,
                total_tokens=calc_total_tokens,
                latency_ms=elapsed_ms,
                estimated_cost_usd=float(cost),
            )

            # Record success audit log with latency and cost
            await self.llm_request_repo.create(
                conversation_id=conversation_id,
                message_id=assistant_msg.id,
                model=model_name,
                prompt_tokens=calc_prompt_tokens,
                completion_tokens=calc_comp_tokens,
                total_tokens=calc_total_tokens,
                estimated_cost=cost,
                latency_ms=elapsed_ms,
                status="success",
            )

            # Store completed response for idempotency caching
            if idempotency_key:
                usage_schema = MessageUsage(
                    prompt_tokens=calc_prompt_tokens,
                    completion_tokens=calc_comp_tokens,
                    total_tokens=calc_total_tokens,
                    estimated_cost_usd=float(cost),
                    latency_ms=elapsed_ms,
                )
                msg_response = MessageResponse(
                    id=assistant_msg.id,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_msg.content,
                    created_at=assistant_msg.created_at,
                    usage=usage_schema,
                )
                await self.idempotency_service.store_response(
                    api_key_id=api_key_id,
                    idempotency_key=idempotency_key,
                    response=msg_response.model_dump(mode="json"),
                )

            # Emit final done SSE event
            done_event = StreamDoneEvent(
                message_id=assistant_msg.id,
                total_tokens=calc_total_tokens,
                estimated_cost_usd=float(cost),
                finish_reason=finish_reason,
            )
            yield f"event: done\ndata: {done_event.model_dump_json()}\n\n"

        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            metrics.record_llm_request(
                provider=settings.llm_provider,
                model=model_name,
                status="error",
                duration_ms=elapsed_ms,
            )
            logger.error(
                "llm_stream_error",
                conversation_id=str(conversation_id),
                model=model_name,
                latency_ms=elapsed_ms,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

            # Record error audit log without saving assistant message
            await self.llm_request_repo.create(
                conversation_id=conversation_id,
                message_id=None,
                model=model_name,
                prompt_tokens=prompt_tokens or 0,
                completion_tokens=len(accumulated_tokens),
                total_tokens=(prompt_tokens or 0) + len(accumulated_tokens),
                estimated_cost=Decimal("0.000000"),
                latency_ms=elapsed_ms,
                status="error",
                error_message=str(exc),
            )

            if idempotency_key:
                await self.idempotency_service.release_lock(api_key_id, idempotency_key)

            err_payload = json.dumps({"error": {"code": "LLM_PROVIDER_ERROR", "message": str(exc)}})
            yield f"event: error\ndata: {err_payload}\n\n"
