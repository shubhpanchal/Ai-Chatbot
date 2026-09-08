"""Integration tests for LLM retry policies, timeouts, and failure handling."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_llm_provider
from app.llm.mock import MockLLMProvider
from app.main import app
from app.models.api_key import APIKey
from app.models.llm_request import LLMRequest
from app.models.message import Message


@pytest.mark.asyncio
async def test_llm_retry_success_after_transient_failures(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify chat service retries transient upstream failures and recovers successfully."""
    _, _, headers = primary_api_key

    # Mock provider that fails twice with TimeoutError, then succeeds on attempt 3
    recovering_mock = MockLLMProvider(
        default_response="Successfully recovered after retry.",
        transient_failures_before_success=2,
    )
    app.dependency_overrides[get_llm_provider] = lambda: recovering_mock

    res_conv = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Retry Test Thread"},
        headers=headers,
    )
    conv_id = res_conv.json()["id"]

    res_msg = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Test transient retry"},
        headers=headers,
    )
    assert res_msg.status_code == 200
    assert "Successfully recovered" in res_msg.json()["content"]
    assert recovering_mock.call_count == 3


@pytest.mark.asyncio
async def test_llm_persistent_timeout_handling(
    async_client: AsyncClient,
    db_session: AsyncSession,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify persistent upstream timeout returns 504 LLM_TIMEOUT and preserves DB integrity."""
    _, _, headers = primary_api_key

    timing_out_mock = MockLLMProvider(
        simulated_error=TimeoutError("Upstream service timed out after 30s"),
        transient_failures_before_success=0,
    )
    app.dependency_overrides[get_llm_provider] = lambda: timing_out_mock

    res_conv = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Timeout Test Thread"},
        headers=headers,
    )
    conv_id = res_conv.json()["id"]

    res_msg = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Trigger timeout"},
        headers=headers,
    )
    assert res_msg.status_code == 504
    data = res_msg.json()
    assert data["error"]["code"] == "LLM_TIMEOUT"

    # Verify no assistant message was saved
    stmt_msgs = select(Message).where(Message.conversation_id == uuid.UUID(conv_id))
    messages = (await db_session.execute(stmt_msgs)).scalars().all()
    # Only the user message exists; no assistant message
    assert len(messages) == 1
    assert messages[0].role == "user"

    # Verify failed LLM request was audited with status='error'
    stmt_req = select(LLMRequest).where(LLMRequest.conversation_id == uuid.UUID(conv_id))
    requests = (await db_session.execute(stmt_req)).scalars().all()
    assert len(requests) == 1
    assert requests[0].status == "error"
    assert "timed out" in (requests[0].error_message or "")


@pytest.mark.asyncio
async def test_llm_unrecoverable_provider_error(
    async_client: AsyncClient,
    db_session: AsyncSession,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify unrecoverable provider error returns 502 LLM_PROVIDER_ERROR and audits failure."""
    _, _, headers = primary_api_key

    fatal_mock = MockLLMProvider(
        simulated_error=RuntimeError("Model decommissioned / unrecoverable failure"),
        transient_failures_before_success=0,
    )
    app.dependency_overrides[get_llm_provider] = lambda: fatal_mock

    res_conv = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Fatal Provider Error Thread"},
        headers=headers,
    )
    conv_id = res_conv.json()["id"]

    res_msg = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Trigger fatal error"},
        headers=headers,
    )
    assert res_msg.status_code == 502
    data = res_msg.json()
    assert data["error"]["code"] == "LLM_PROVIDER_ERROR"

    # Verify no assistant message was saved
    stmt_msgs = select(Message).where(Message.conversation_id == uuid.UUID(conv_id))
    messages = (await db_session.execute(stmt_msgs)).scalars().all()
    assert len(messages) == 1
    assert messages[0].role == "user"

    # Verify failed LLM request was audited with status='error'
    stmt_req = select(LLMRequest).where(LLMRequest.conversation_id == uuid.UUID(conv_id))
    requests = (await db_session.execute(stmt_req)).scalars().all()
    assert len(requests) == 1
    assert requests[0].status == "error"
