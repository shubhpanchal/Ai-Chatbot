"""Integration tests for SSE streaming cancellation and provider failure behavior."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import RedisClient
from app.llm.base import LLMMessage
from app.llm.mock import MockLLMProvider
from app.models.api_key import APIKey
from app.models.conversation import Conversation
from app.models.llm_request import LLMRequest
from app.models.message import Message
from app.repositories.conversation import ConversationRepository
from app.repositories.llm_request import LLMRequestRepository
from app.repositories.message import MessageRepository
from app.services.chat import ChatService
from app.services.cost import CostCalculatorService
from app.services.idempotency import IdempotencyService
from tests.integration.test_streaming_api import parse_sse_events


@pytest.mark.asyncio
async def test_streaming_client_disconnect_cancellation(
    db_session: AsyncSession,
    redis_client: RedisClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify client disconnect immediately cancels upstream generation, marks llm_requests as cancelled, and does not persist assistant message."""
    api_key, _, _ = primary_api_key

    # 1. Setup conversation
    conv_repo = ConversationRepository(db_session)
    msg_repo = MessageRepository(db_session)
    llm_req_repo = LLMRequestRepository(db_session)
    cost_calc = CostCalculatorService()
    idempotency_svc = IdempotencyService(redis_client)

    conv = Conversation(
        id=uuid.uuid4(),
        api_key_id=api_key.id,
        title="Disconnect Test",
    )
    db_session.add(conv)
    await db_session.commit()

    # Provider with many tokens
    mock_llm = MockLLMProvider(
        default_response="one two three four five six seven eight nine ten",
        simulated_latency_ms=0,
    )
    chat_svc = ChatService(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        llm_request_repo=llm_req_repo,
        llm_provider=mock_llm,
        cost_calculator=cost_calc,
        idempotency_service=idempotency_svc,
    )

    # Disconnect callback that triggers after 2 tokens
    token_count = 0

    async def simulate_disconnect() -> bool:
        nonlocal token_count
        return token_count >= 2

    context_messages = [
        LLMMessage(role="system", content="You are an assistant."),
        LLMMessage(role="user", content="Count to ten."),
    ]

    yielded_events: list[str] = []
    async for event in chat_svc.stream_message(
        conversation_id=conv.id,
        api_key_id=api_key.id,
        context_messages=context_messages,
        is_disconnected=simulate_disconnect,
    ):
        yielded_events.append(event)
        token_count += 1

    # Verify stream terminated early (did not yield all 10 tokens + done event)
    raw_output = "".join(yielded_events)
    events = parse_sse_events(raw_output)
    done_events = [d for t, d in events if t == "done"]
    assert len(done_events) == 0  # No done event on cancellation

    # 2. Verify Database State: ZERO assistant messages persisted!
    stmt_msgs = select(Message).where(
        Message.conversation_id == conv.id,
        Message.role == "assistant",
    )
    assistant_msgs = (await db_session.execute(stmt_msgs)).scalars().all()
    assert len(assistant_msgs) == 0

    # 3. Verify llm_requests record has status = 'cancelled'
    stmt_req = select(LLMRequest).where(LLMRequest.conversation_id == conv.id)
    reqs = (await db_session.execute(stmt_req)).scalars().all()
    assert len(reqs) == 1
    req = reqs[0]
    assert req.status == "cancelled"
    assert req.message_id is None
    assert "Client disconnected" in (req.error_message or "")


@pytest.mark.asyncio
async def test_streaming_provider_failure_handling(
    db_session: AsyncSession,
    redis_client: RedisClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify that upstream provider failures during streaming log error, emit error SSE, and do not save assistant message."""
    api_key, _, _ = primary_api_key

    conv_repo = ConversationRepository(db_session)
    msg_repo = MessageRepository(db_session)
    llm_req_repo = LLMRequestRepository(db_session)
    cost_calc = CostCalculatorService()
    idempotency_svc = IdempotencyService(redis_client)

    conv = Conversation(
        id=uuid.uuid4(),
        api_key_id=api_key.id,
        title="Provider Error Test",
    )
    db_session.add(conv)
    await db_session.commit()

    # Provider configured to fail
    mock_llm = MockLLMProvider(
        simulated_error=RuntimeError("Upstream LLM network disconnection"),
    )
    chat_svc = ChatService(
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        llm_request_repo=llm_req_repo,
        llm_provider=mock_llm,
        cost_calculator=cost_calc,
        idempotency_service=idempotency_svc,
    )

    context_messages = [LLMMessage(role="user", content="Trigger failure")]

    yielded_events: list[str] = []
    async for event in chat_svc.stream_message(
        conversation_id=conv.id,
        api_key_id=api_key.id,
        context_messages=context_messages,
    ):
        yielded_events.append(event)

    # Verify error SSE event was emitted
    raw_output = "".join(yielded_events)
    events = parse_sse_events(raw_output)
    error_events = [d for t, d in events if t == "error"]
    assert len(error_events) == 1
    assert "Upstream LLM network disconnection" in str(error_events[0])

    # Verify no assistant message was persisted
    stmt_msgs = select(Message).where(
        Message.conversation_id == conv.id,
        Message.role == "assistant",
    )
    assistant_msgs = (await db_session.execute(stmt_msgs)).scalars().all()
    assert len(assistant_msgs) == 0

    # Verify llm_requests record has status = 'error'
    stmt_req = select(LLMRequest).where(LLMRequest.conversation_id == conv.id)
    reqs = (await db_session.execute(stmt_req)).scalars().all()
    assert len(reqs) == 1
    assert reqs[0].status == "error"
