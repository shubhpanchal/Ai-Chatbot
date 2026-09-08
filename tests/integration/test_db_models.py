"""Integration tests for SQLAlchemy models, constraints, and relationships in PostgreSQL."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_raw_api_key, hash_api_key
from app.models.api_key import APIKey
from app.models.conversation import Conversation
from app.models.llm_request import LLMRequest
from app.models.message import Message


@pytest.mark.asyncio
async def test_full_database_model_lifecycle(db_session: AsyncSession) -> None:
    """Test creating APIKey, Conversation, Messages, and LLMRequest with foreign keys."""
    # 1. Create API Key
    raw_key = generate_raw_api_key("ak_test_lifecycle")
    key_hash = hash_api_key(raw_key, settings.api_key_secret)
    api_key = APIKey(
        name="lifecycle-test-key",
        key_hash=key_hash,
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.flush()

    assert api_key.id is not None
    assert api_key.created_at is not None

    # 2. Create Conversation owned by API Key
    conversation = Conversation(
        api_key_id=api_key.id,
        title="PostgreSQL Async Integration",
        system_prompt="You are a database expert.",
    )
    db_session.add(conversation)
    await db_session.flush()

    assert conversation.id is not None
    assert conversation.api_key_id == api_key.id
    assert conversation.is_deleted is False

    # 3. Create Messages in sequence
    msg_user = Message(
        conversation_id=conversation.id,
        role="user",
        content="What is MVCC in PostgreSQL?",
    )
    db_session.add(msg_user)
    await db_session.flush()

    msg_assistant = Message(
        conversation_id=conversation.id,
        role="assistant",
        content="Multi-Version Concurrency Control allows readers not to block writers.",
    )
    db_session.add(msg_assistant)
    await db_session.flush()

    # 4. Create LLMRequest audit record
    llm_req = LLMRequest(
        conversation_id=conversation.id,
        message_id=msg_assistant.id,
        model="gpt-4o-mini",
        prompt_tokens=45,
        completion_tokens=60,
        total_tokens=105,
        estimated_cost=Decimal("0.000031"),
        latency_ms=620,
        status="success",
    )
    db_session.add(llm_req)
    await db_session.flush()

    # 5. Query and verify relations
    stmt = select(Conversation).where(Conversation.id == conversation.id)
    result = await db_session.execute(stmt)
    fetched_conv = result.scalar_one()

    assert fetched_conv.title == "PostgreSQL Async Integration"
    assert len(fetched_conv.messages) == 2
    assert fetched_conv.messages[0].role == "user"
    assert fetched_conv.messages[1].role == "assistant"
    assert len(fetched_conv.llm_requests) == 1
    assert fetched_conv.llm_requests[0].model == "gpt-4o-mini"
    assert fetched_conv.llm_requests[0].status == "success"

    # Clean up test rows
    await db_session.delete(api_key)
    await db_session.commit()
