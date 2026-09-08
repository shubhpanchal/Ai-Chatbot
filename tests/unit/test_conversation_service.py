"""Unit tests for ConversationService logic and tenant boundary enforcement."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConversationNotFoundError, ValidationError
from app.models.api_key import APIKey
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository
from app.schemas.conversation import ConversationCreate
from app.services.conversation import ConversationService


@pytest.mark.asyncio
async def test_conversation_service_create_and_get(
    db_session: AsyncSession,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify ConversationService creates and retrieves conversations."""
    key, _, _ = primary_api_key
    conv_repo = ConversationRepository(db_session)
    msg_repo = MessageRepository(db_session)
    service = ConversationService(conv_repo, msg_repo)

    # Valid creation
    payload = ConversationCreate(
        title="Service Test",
        system_prompt="Custom Instructor",
    )
    created = await service.create_conversation(key.id, payload)
    assert created.id is not None
    assert created.title == "Service Test"
    assert created.system_prompt == "Custom Instructor"

    # Get conversation details
    detail = await service.get_conversation(created.id, key.id)
    assert detail.id == created.id
    assert detail.title == "Service Test"
    assert len(detail.messages) == 0
    assert detail.usage_summary.total_requests == 0


@pytest.mark.asyncio
async def test_conversation_service_validation_errors(
    db_session: AsyncSession,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify ConversationService rejects empty titles and invalid pagination."""
    key, _, _ = primary_api_key
    conv_repo = ConversationRepository(db_session)
    msg_repo = MessageRepository(db_session)
    service = ConversationService(conv_repo, msg_repo)

    # Empty title
    with pytest.raises(ValidationError, match="title cannot be empty"):
        await service.create_conversation(key.id, ConversationCreate(title="   "))

    # Invalid page number
    with pytest.raises(ValidationError, match="Page number must be greater than or equal to 1"):
        await service.list_conversations(key.id, page=0, page_size=20)

    # Invalid page size
    with pytest.raises(ValidationError, match="Page size must be between 1 and 100"):
        await service.list_conversations(key.id, page=1, page_size=0)

    with pytest.raises(ValidationError, match="Page size must be between 1 and 100"):
        await service.list_conversations(key.id, page=1, page_size=101)


@pytest.mark.asyncio
async def test_conversation_service_not_found_and_isolation(
    db_session: AsyncSession,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    secondary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify ConversationService raises 404 on missing conversation and cross-tenant access."""
    key_1, _, _ = primary_api_key
    key_2, _, _ = secondary_api_key
    conv_repo = ConversationRepository(db_session)
    msg_repo = MessageRepository(db_session)
    service = ConversationService(conv_repo, msg_repo)

    created = await service.create_conversation(
        key_1.id, ConversationCreate(title="Tenant 1 Thread")
    )

    # Non-existent ID
    random_id = uuid.uuid4()
    with pytest.raises(ConversationNotFoundError):
        await service.get_conversation(random_id, key_1.id)

    # Cross-tenant access: Key 2 cannot get Key 1's conversation
    with pytest.raises(ConversationNotFoundError):
        await service.get_conversation(created.id, key_2.id)

    # Cross-tenant delete: Key 2 cannot delete Key 1's conversation
    with pytest.raises(ConversationNotFoundError):
        await service.delete_conversation(created.id, key_2.id)

    # Owner can delete
    await service.delete_conversation(created.id, key_1.id)

    # Once deleted, get_conversation raises ConversationNotFoundError
    with pytest.raises(ConversationNotFoundError):
        await service.get_conversation(created.id, key_1.id)

    # Re-deleting raises ConversationNotFoundError
    with pytest.raises(ConversationNotFoundError):
        await service.delete_conversation(created.id, key_1.id)
