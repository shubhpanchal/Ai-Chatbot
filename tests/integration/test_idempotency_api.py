"""Integration tests for Idempotency-Key support on message generation endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.mock import MockLLMProvider
from app.models.api_key import APIKey
from app.models.llm_request import LLMRequest


@pytest.mark.asyncio
async def test_idempotency_replay_returns_cached_response(
    async_client: AsyncClient,
    db_session: AsyncSession,
    mock_llm: MockLLMProvider,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify replayed request with same Idempotency-Key returns cached response without duplicate LLM calls."""
    _, _, headers = primary_api_key
    idem_key = str(uuid.uuid4())

    # Create conversation
    res_conv = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Idempotency Test Thread"},
        headers=headers,
    )
    conv_id = res_conv.json()["id"]

    request_headers = {**headers, "Idempotency-Key": idem_key}

    # 1. First request
    res1 = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Calculate 2 + 2"},
        headers=request_headers,
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert mock_llm.call_count == 1

    # 2. Replay identical request with same Idempotency-Key
    res2 = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Calculate 2 + 2"},
        headers=request_headers,
    )
    assert res2.status_code == 200
    data2 = res2.json()

    # Verify identical response payload
    assert data1["id"] == data2["id"]
    assert data1["content"] == data2["content"]
    assert data1["created_at"] == data2["created_at"]

    # Verify MockLLM was NOT invoked a second time
    assert mock_llm.call_count == 1

    # Verify only ONE LLM request was logged and billed
    stmt = select(LLMRequest).where(LLMRequest.conversation_id == uuid.UUID(conv_id))
    records = (await db_session.execute(stmt)).scalars().all()
    assert len(records) == 1


@pytest.mark.asyncio
async def test_idempotency_keys_are_isolated_per_tenant(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    secondary_api_key: tuple[APIKey, str, dict[str, str]],
    mock_llm: MockLLMProvider,
) -> None:
    """Verify the same idempotency key string used by different tenants does not leak cached responses."""
    _, _, headers_a = primary_api_key
    _, _, headers_b = secondary_api_key
    shared_idem_key = "client-retry-key-001"

    # Tenant A creates conversation and sends message
    res_conv_a = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Tenant A Thread"},
        headers=headers_a,
    )
    conv_a_id = res_conv_a.json()["id"]

    res_msg_a = await async_client.post(
        f"/api/v1/conversations/{conv_a_id}/messages",
        json={"content": "Message from Tenant A"},
        headers={**headers_a, "Idempotency-Key": shared_idem_key},
    )
    assert res_msg_a.status_code == 200
    data_a = res_msg_a.json()

    # Tenant B creates conversation and sends message with SAME Idempotency-Key string
    res_conv_b = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Tenant B Thread"},
        headers=headers_b,
    )
    conv_b_id = res_conv_b.json()["id"]

    res_msg_b = await async_client.post(
        f"/api/v1/conversations/{conv_b_id}/messages",
        json={"content": "Message from Tenant B"},
        headers={**headers_b, "Idempotency-Key": shared_idem_key},
    )
    assert res_msg_b.status_code == 200
    data_b = res_msg_b.json()

    # Each tenant got a unique response and separate LLM execution
    assert data_a["id"] != data_b["id"]
    assert mock_llm.call_count == 2
