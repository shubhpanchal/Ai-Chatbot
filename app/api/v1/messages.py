"""Message generation endpoints for synchronous and streaming LLM interactions."""

import uuid

from fastapi import APIRouter, Depends, Header, status

from app.api.deps import get_chat_service, get_current_api_key
from app.models.api_key import APIKey
from app.schemas.message import MessageCreate, MessageResponse
from app.services.chat import ChatService

router = APIRouter(prefix="/conversations/{conversation_id}/messages", tags=["Messages"])


@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Send message (synchronous)",
    description="Send a message, reconstruct context history, execute LLM call, and return assistant response.",
)
async def send_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Optional unique idempotency key to prevent duplicate LLM calls on client retries.",
    ),
    current_key: APIKey = Depends(get_current_api_key),
    chat_service: ChatService = Depends(get_chat_service),
) -> MessageResponse:
    """Execute synchronous conversational turn with LLM and return complete assistant reply."""
    return await chat_service.send_message(
        conversation_id=conversation_id,
        api_key_id=current_key.id,
        content=payload.content,
        idempotency_key=idempotency_key,
    )
