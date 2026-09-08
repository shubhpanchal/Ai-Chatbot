"""Message generation endpoints for synchronous and streaming LLM interactions."""

import uuid

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import check_rate_limit, get_chat_service, get_current_api_key
from app.models.api_key import APIKey
from app.schemas.message import MessageCreate, MessageResponse
from app.services.chat import ChatService

router = APIRouter(
    prefix="/conversations/{conversation_id}/messages",
    tags=["Messages"],
    dependencies=[Depends(check_rate_limit)],
)


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


@router.post(
    "/stream",
    status_code=status.HTTP_200_OK,
    summary="Send message (streaming SSE)",
    description="Stream the LLM response incrementally as Server-Sent Events (SSE).",
    response_class=StreamingResponse,
)
async def send_message_stream(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    request: Request,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Optional unique idempotency key for request tracking.",
    ),
    current_key: APIKey = Depends(get_current_api_key),
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """Execute streaming conversational turn with LLM and emit SSE token/done events."""
    _, context_messages, cached = await chat_service.prepare_stream_turn(
        conversation_id=conversation_id,
        api_key_id=current_key.id,
        content=payload.content,
        idempotency_key=idempotency_key,
    )

    generator = chat_service.stream_message(
        conversation_id=conversation_id,
        api_key_id=current_key.id,
        context_messages=context_messages,
        cached_response=cached,
        idempotency_key=idempotency_key,
        is_disconnected=request.is_disconnected,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
