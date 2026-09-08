"""Unit tests for repository data access components."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_raw_api_key, hash_api_key
from app.models.api_key import APIKey
from app.models.llm_request import LLMRequest
from app.repositories.api_key import APIKeyRepository
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository


@pytest.mark.asyncio
async def test_api_key_repository(db_session: AsyncSession) -> None:
    """Verify APIKeyRepository hash lookup and last_used timestamp update."""
    repo = APIKeyRepository(db_session)
    raw_key = generate_raw_api_key(prefix="ak_repo_test")
    key_hash = hash_api_key(raw_key, settings.api_key_secret)

    # Insert test key
    api_key = APIKey(
        id=uuid.uuid4(),
        name="Repo Test Key",
        key_hash=key_hash,
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()

    # Query by hash
    fetched = await repo.get_by_key_hash(key_hash)
    assert fetched is not None
    assert fetched.id == api_key.id
    assert fetched.name == "Repo Test Key"

    # Query by unknown hash
    unknown = await repo.get_by_key_hash("nonexistent_hash_digest")
    assert unknown is None

    # Update last_used
    assert fetched.last_used_at is None
    await repo.update_last_used(api_key.id)
    refreshed = await repo.get_by_id(api_key.id)
    assert refreshed is not None
    assert refreshed.last_used_at is not None


@pytest.mark.asyncio
async def test_conversation_repository_crud_and_soft_delete(
    db_session: AsyncSession,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    secondary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify ConversationRepository creation, tenant isolation, and soft delete."""
    key_1, _, _ = primary_api_key
    key_2, _, _ = secondary_api_key
    repo = ConversationRepository(db_session)

    # Create conversation for Key 1
    conv = await repo.create(
        api_key_id=key_1.id,
        title="Repo Test Conversation",
        system_prompt="Test System Prompt",
    )
    assert conv.id is not None
    assert conv.title == "Repo Test Conversation"
    assert conv.api_key_id == key_1.id
    assert conv.deleted_at is None

    # Key 1 can read
    fetched = await repo.get_by_id(conv.id, key_1.id)
    assert fetched is not None
    assert fetched.id == conv.id

    # Key 2 CANNOT read (cross-tenant isolation)
    cross_tenant = await repo.get_by_id(conv.id, key_2.id)
    assert cross_tenant is None

    # List conversations for Key 1
    items, total = await repo.list_by_api_key(key_1.id, page=1, page_size=10)
    assert total >= 1
    assert any(item.id == conv.id for item in items)

    # Soft delete conversation
    deleted = await repo.soft_delete(conv.id, key_1.id)
    assert deleted is True

    # After soft delete, standard get_by_id returns None
    assert await repo.get_by_id(conv.id, key_1.id) is None

    # include_deleted=True returns the record
    deleted_record = await repo.get_by_id(conv.id, key_1.id, include_deleted=True)
    assert deleted_record is not None
    assert deleted_record.deleted_at is not None

    # Re-deleting returns False
    assert await repo.soft_delete(conv.id, key_1.id) is False


@pytest.mark.asyncio
async def test_conversation_repository_usage_stats(
    db_session: AsyncSession,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify usage stats calculation on ConversationRepository."""
    key, _, _ = primary_api_key
    conv_repo = ConversationRepository(db_session)

    conv = await conv_repo.create(api_key_id=key.id, title="Stats Test")

    # Initial stats should be zeros
    stats = await conv_repo.get_usage_stats(conv.id)
    assert stats == {"total_requests": 0, "total_tokens": 0, "estimated_cost_usd": 0.0}

    # Add dummy LLM request audit entries
    req1 = LLMRequest(
        conversation_id=conv.id,
        model="gpt-4o-mini",
        prompt_tokens=50,
        completion_tokens=25,
        total_tokens=75,
        estimated_cost=Decimal("0.000015"),
        latency_ms=350,
        status="success",
    )
    req2 = LLMRequest(
        conversation_id=conv.id,
        model="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        estimated_cost=Decimal("0.000030"),
        latency_ms=450,
        status="success",
    )
    db_session.add_all([req1, req2])
    await db_session.commit()

    # Re-query stats
    updated_stats = await conv_repo.get_usage_stats(conv.id)
    assert updated_stats["total_requests"] == 2
    assert updated_stats["total_tokens"] == 225
    assert abs(updated_stats["estimated_cost_usd"] - 0.000045) < 1e-6


@pytest.mark.asyncio
async def test_message_repository(
    db_session: AsyncSession,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify MessageRepository creation, listing, and ordering."""
    key, _, _ = primary_api_key
    conv_repo = ConversationRepository(db_session)
    msg_repo = MessageRepository(db_session)

    conv = await conv_repo.create(api_key_id=key.id, title="Message Repo Test")

    # Create messages
    m1 = await msg_repo.create(conversation_id=conv.id, role="user", content="Hello!")
    m2 = await msg_repo.create(
        conversation_id=conv.id, role="assistant", content="Hi! How can I help?"
    )

    assert m1.id is not None
    assert m2.id is not None

    messages = await msg_repo.list_by_conversation(conv.id)
    assert len(messages) == 2
    assert messages[0].content == "Hello!"
    assert messages[1].content == "Hi! How can I help!" or messages[1].content.startswith("Hi!")
    assert await msg_repo.count_by_conversation(conv.id) == 2
