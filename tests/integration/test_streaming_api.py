"""Integration tests for Server-Sent Events (SSE) streaming endpoint."""

import json
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.mock import MockLLMProvider
from app.models.api_key import APIKey
from app.models.llm_request import LLMRequest
from app.models.message import Message


def parse_sse_events(raw_body: str) -> list[tuple[str, dict[str, Any]]]:
    """Helper to parse raw SSE text stream into list of (event_type, json_data) tuples."""
    events: list[tuple[str, dict[str, Any]]] = []
    blocks = raw_body.strip().split("\n\n")
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().split("\n")
        event_type = "message"
        data_str = ""
        for line in lines:
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_str = line.split(":", 1)[1].strip()
        if data_str:
            events.append((event_type, json.loads(data_str)))
    return events


@pytest.mark.asyncio
async def test_streaming_chat_happy_path(
    async_client: AsyncClient,
    db_session: AsyncSession,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    mock_llm: MockLLMProvider,
) -> None:
    """Verify happy path SSE streaming with incremental tokens, done event, and database persistence."""
    _, _, headers = primary_api_key

    # 1. Create conversation
    res_conv = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Streaming Test Conversation", "system_prompt": "You are a streaming bot."},
        headers=headers,
    )
    assert res_conv.status_code == 201
    conv_id = res_conv.json()["id"]

    # 2. Request SSE stream
    res_stream = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages/stream",
        json={"content": "Explain async gather in Python"},
        headers=headers,
    )
    assert res_stream.status_code == 200
    assert "text/event-stream" in res_stream.headers.get("content-type", "")

    # 3. Parse SSE events
    events = parse_sse_events(res_stream.text)
    assert len(events) > 1

    token_events = [data for event_type, data in events if event_type == "token"]
    done_events = [data for event_type, data in events if event_type == "done"]

    assert len(token_events) > 0
    assert len(done_events) == 1

    # Verify token sequence indices
    for i, tok in enumerate(token_events):
        assert tok["index"] == i
        assert isinstance(tok["token"], str)

    # Reconstruct streamed text
    streamed_text = "".join(str(tok["token"]) for tok in token_events)
    assert "MockLLMProvider" in streamed_text

    # Verify done event metadata
    done_data = done_events[0]
    assistant_msg_id = done_data["message_id"]
    assert assistant_msg_id is not None
    assert int(done_data["total_tokens"]) > 0
    assert float(done_data["estimated_cost_usd"]) > 0
    assert done_data["finish_reason"] == "stop"

    # 4. Verify Database Persistence
    stmt = (
        select(Message)
        .where(Message.conversation_id == uuid.UUID(conv_id))
        .order_by(Message.created_at.asc())
    )
    messages = (await db_session.execute(stmt)).scalars().all()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Explain async gather in Python"
    assert messages[1].role == "assistant"
    assert messages[1].content == streamed_text
    assert str(messages[1].id) == assistant_msg_id

    # Verify llm_requests audit log
    stmt_llm = select(LLMRequest).where(LLMRequest.conversation_id == uuid.UUID(conv_id))
    llm_reqs = (await db_session.execute(stmt_llm)).scalars().all()
    assert len(llm_reqs) == 1
    req = llm_reqs[0]
    assert req.status == "success"
    assert req.message_id == messages[1].id
    assert req.prompt_tokens > 0
    assert req.completion_tokens > 0
    assert req.estimated_cost > 0


@pytest.mark.asyncio
async def test_streaming_chat_cross_tenant_isolation(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    secondary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify Tenant B cannot stream messages to Tenant A's conversation (HTTP 404)."""
    _, _, headers_a = primary_api_key
    _, _, headers_b = secondary_api_key

    # Tenant A creates conversation
    res_conv = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Tenant A Secret Thread"},
        headers=headers_a,
    )
    conv_id = res_conv.json()["id"]

    # Tenant B tries to stream message to Tenant A conversation
    res_stream = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages/stream",
        json={"content": "Attempting unauthorized stream"},
        headers=headers_b,
    )
    assert res_stream.status_code == 404
    assert res_stream.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_streaming_chat_validation_errors(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify empty or invalid payloads return HTTP 422 JSON errors before streaming starts."""
    _, _, headers = primary_api_key

    res_conv = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Validation Thread"},
        headers=headers,
    )
    conv_id = res_conv.json()["id"]

    # Empty content
    res_empty = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages/stream",
        json={"content": "   "},
        headers=headers,
    )
    assert res_empty.status_code == 422
    assert res_empty.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_streaming_chat_idempotency_replay(
    async_client: AsyncClient,
    db_session: AsyncSession,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    mock_llm: MockLLMProvider,
) -> None:
    """Verify streaming endpoint replays cached response when re-invoked with same Idempotency-Key."""
    _, _, headers = primary_api_key
    idem_key = f"idem-stream-{uuid.uuid4()}"

    res_conv = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Idempotent Stream Thread"},
        headers=headers,
    )
    conv_id = res_conv.json()["id"]

    request_headers = {**headers, "Idempotency-Key": idem_key}

    # 1. First streaming request
    res1 = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages/stream",
        json={"content": "Idempotent streaming test prompt"},
        headers=request_headers,
    )
    assert res1.status_code == 200
    events1 = parse_sse_events(res1.text)
    done1 = [d for t, d in events1 if t == "done"][0]
    assert mock_llm.call_count == 1

    # 2. Replayed streaming request with SAME key
    res2 = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages/stream",
        json={"content": "Idempotent streaming test prompt"},
        headers=request_headers,
    )
    assert res2.status_code == 200
    events2 = parse_sse_events(res2.text)
    done2 = [d for t, d in events2 if t == "done"][0]

    # Verify identical message ID replayed
    assert done1["message_id"] == done2["message_id"]
    # MockLLM was NOT invoked a second time
    assert mock_llm.call_count == 1

    # Verify only ONE LLM request was recorded
    stmt = select(LLMRequest).where(LLMRequest.conversation_id == uuid.UUID(conv_id))
    records = (await db_session.execute(stmt)).scalars().all()
    assert len(records) == 1
