"""Conversation lifecycle endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_conversation_service, get_current_api_key
from app.models.api_key import APIKey
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
    PaginatedConversationsResponse,
)
from app.services.conversation import ConversationService

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create conversation",
    description="Create a new conversation thread owned by the authenticated API key.",
)
async def create_conversation(
    payload: ConversationCreate,
    current_key: APIKey = Depends(get_current_api_key),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationResponse:
    """Create a new conversation thread for the authenticated API key."""
    return await service.create_conversation(
        api_key_id=current_key.id,
        data=payload,
    )


@router.get(
    "",
    response_model=PaginatedConversationsResponse,
    status_code=status.HTTP_200_OK,
    summary="List conversations",
    description="List all active conversations owned by the caller with pagination.",
)
async def list_conversations(
    page: int = Query(default=1, ge=1, description="Page number (>= 1)."),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page (1-100).",
    ),
    current_key: APIKey = Depends(get_current_api_key),
    service: ConversationService = Depends(get_conversation_service),
) -> PaginatedConversationsResponse:
    """Retrieve paginated conversations belonging to the authenticated API key."""
    return await service.list_conversations(
        api_key_id=current_key.id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get conversation details",
    description="Retrieve a conversation thread with all messages and token usage statistics.",
)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_key: APIKey = Depends(get_current_api_key),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationDetailResponse:
    """Fetch conversation details, messages, and usage summary for the authenticated owner."""
    return await service.get_conversation(
        conversation_id=conversation_id,
        api_key_id=current_key.id,
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete conversation",
    description="Soft-delete a conversation thread owned by the authenticated API key.",
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_key: APIKey = Depends(get_current_api_key),
    service: ConversationService = Depends(get_conversation_service),
) -> Response:
    """Soft-delete an active conversation owned by the caller."""
    await service.delete_conversation(
        conversation_id=conversation_id,
        api_key_id=current_key.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
