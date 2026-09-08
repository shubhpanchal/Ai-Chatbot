"""Integration tests for synchronous chat endpoint and database persistence."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import APIKey
from app.models.llm_request import LLMRequest
from app.models.message import Message


@pytest.mark.asyncio
async def test_synchronous_chat_success(
    async_client: AsyncClient,
    db_session: AsyncSession,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify POST /api/v1/conversations/{id}/messages executes synchronous chat turn, persists messages and audits."""
    _, _, headers = primary_api_key

    # 1. Create a conversation
    res_conv = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Chat Test", "system_prompt": "You are a test assistant."},
        headers=headers,
    )
    assert res_conv.status_code == 201
    conv_id = res_conv.json()["id"]

    # 2. Send first user message
    res_msg = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "What is Python asyncio?"},
        headers=headers,
    )
    assert res_msg.status_code == 200
    msg_data = res_msg.json()

    assert msg_data["conversation_id"] == conv_id
    assert msg_data["role"] == "assistant"
    assert "MockLLMProvider" in msg_data["content"]
    assert "usage" in msg_data
    usage = msg_data["usage"]
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
    assert usage["estimated_cost_usd"] > 0
    assert usage["latency_ms"] >= 0

    # 3. Verify Database Persistence
    stmt_msgs = (
        select(Message)
        .where(Message.conversation_id == uuid.UUID(conv_id))
        .order_by(Message.created_at.asc())
    )
    res_db_msgs = await db_session.execute(stmt_msgs)
    db_messages = list(res_db_msgs.scalars().all())

    assert len(db_messages) == 2
    assert db_messages[0].role == "user"
    assert db_messages[0].content == "What is Python asyncio?"
    assert db_messages[1].role == "assistant"
    assert db_messages[1].id == uuid.UUID(msg_data["id"])

    # 4. Verify LLM Request Audit Log Persistence
    stmt_req = select(LLMRequest).where(LLMRequest.conversation_id == uuid.UUID(conv_id))
    res_req = await db_session.execute(stmt_req)
    db_requests = list(res_req.scalars().all())

    assert len(db_requests) == 1
    assert db_requests[0].status == "success"
    assert db_requests[0].message_id == uuid.UUID(msg_data["id"])
    assert db_requests[0].total_tokens == usage["total_tokens"]


@pytest.mark.asyncio
async def test_synchronous_chat_multi_turn_history(
    async_client: AsyncClient,
    db_session: AsyncSession,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify multi-turn conversations accumulate history sequentially."""
    _, _, headers = primary_api_key

    res_conv = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Multi Turn Thread"},
        headers=headers,
    )
    conv_id = res_conv.json()["id"]

    # Turn 1
    await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "First turn"},
        headers=headers,
    )

    # Turn 2
    await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Second turn"},
        headers=headers,
    )

    # Verify conversation detail endpoint has 4 messages and updated usage summary
    res_detail = await async_client.get(
        f"/api/v1/conversations/{conv_id}",
        headers=headers,
    )
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert len(detail["messages"]) == 4
    assert detail["usage_summary"]["total_requests"] == 2
    assert detail["usage_summary"]["total_tokens"] > 0


@pytest.mark.asyncio
async def test_synchronous_chat_validation_and_not_found(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify error responses for empty message bodies and non-existent conversations."""
    _, _, headers = primary_api_key

    # Non-existent conversation -> 404 CONVERSATION_NOT_FOUND
    random_id = uuid.uuid4()
    res_404 = await async_client.post(
        f"/api/v1/conversations/{random_id}/messages",
        json={"content": "Hello"},
        headers=headers,
    )
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"

    # Create real conversation
    res_conv = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Validation Thread"},
        headers=headers,
    )
    conv_id = res_conv.json()["id"]

    # Empty content -> 422 VALIDATION_ERROR
    res_empty = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "   "},
        headers=headers,
    )
    assert res_empty.status_code == 422
    assert res_empty.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_synchronous_chat_cross_tenant_rejection(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    secondary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify Tenant B cannot send messages to Tenant A's conversation."""
    _, _, headers_a = primary_api_key
    _, _, headers_b = secondary_api_key

    res_conv = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Tenant A Private Thread"},
        headers=headers_a,
    )
    conv_id = res_conv.json()["id"]

    # Tenant B tries to message Tenant A's conversation -> 404
    res_cross = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Tenant B intrusion attempt"},
        headers=headers_b,
    )
    assert res_cross.status_code == 404
    assert res_cross.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"
