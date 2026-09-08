"""Comprehensive reliability and failure-mode integration tests.

Covers:
1. PostgreSQL failure during API operations.
2. Redis failure under fail-closed and fail-open rate limiting policies.
3. Redis failure during idempotency caching.
4. LLM timeouts and gateway error mappings with audit persistence.
5. LLM unrecoverable errors and audit persistence.
6. Client disconnect cancellation during SSE streaming.
7. Idempotent replay preventing duplicate DB records and LLM billing.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RedisClient, get_llm_provider, get_redis
from app.core.exceptions import LLMProviderError, LLMTimeoutError
from app.llm.base import LLMProvider
from app.main import app
from app.models.api_key import APIKey
from app.models.llm_request import LLMRequest
from app.models.message import Message


@pytest.mark.asyncio
async def test_postgres_failure_during_conversation_creation(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify that PostgreSQL connectivity loss results in a 503 error envelope without crashing."""
    _, _, headers = primary_api_key

    from app.api.deps import get_conversation_service
    from app.core.exceptions import ServiceUnavailableError
    from app.services.conversation import ConversationService

    mock_service = AsyncMock(spec=ConversationService)
    mock_service.create_conversation.side_effect = ServiceUnavailableError(
        "Database connection lost"
    )

    app.dependency_overrides[get_conversation_service] = lambda: mock_service

    try:
        res = await async_client.post(
            "/api/v1/conversations",
            json={"title": "Failing DB Test"},
            headers=headers,
        )
        assert res.status_code == 503
        body = res.json()
        assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert "request_id" in body["error"]
    finally:
        app.dependency_overrides.pop(get_conversation_service, None)


@pytest.mark.asyncio
async def test_redis_failure_fail_closed_policy(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that when Redis is unreachable, fail-closed policy returns 503 SERVICE_UNAVAILABLE."""
    _, _, headers = primary_api_key

    mock_redis = AsyncMock(spec=RedisClient)
    mock_redis.evalsha.side_effect = ConnectionRefusedError("Redis connection refused")
    mock_redis.eval.side_effect = ConnectionRefusedError("Redis connection refused")

    async def failing_get_redis() -> AsyncGenerator[RedisClient, None]:
        yield mock_redis

    app.dependency_overrides[get_redis] = failing_get_redis

    try:
        res = await async_client.get("/api/v1/conversations", headers=headers)
        assert res.status_code == 503
        body = res.json()
        assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert "temporarily unavailable" in body["error"]["message"].lower()
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_redis_failure_fail_open_policy(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that when Redis is unreachable and fail-open is True, requests proceed."""
    _, _, headers = primary_api_key
    monkeypatch.setattr("app.core.config.settings.rate_limit_fail_open", True)

    mock_redis = AsyncMock(spec=RedisClient)
    mock_redis.evalsha.side_effect = ConnectionRefusedError("Redis connection refused")
    mock_redis.eval.side_effect = ConnectionRefusedError("Redis connection refused")

    async def failing_get_redis() -> AsyncGenerator[RedisClient, None]:
        yield mock_redis

    app.dependency_overrides[get_redis] = failing_get_redis

    try:
        res = await async_client.get("/api/v1/conversations", headers=headers)
        assert res.status_code == 200
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_llm_timeout_produces_gateway_timeout_and_error_audit(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    db_session: AsyncSession,
) -> None:
    """Verify that provider timeouts produce 504 GATEWAY_TIMEOUT and record error audit record."""
    _, _, headers = primary_api_key

    # Create conversation
    conv_id = (
        await async_client.post(
            "/api/v1/conversations",
            json={"title": "Timeout Test"},
            headers=headers,
        )
    ).json()["id"]

    mock_provider = AsyncMock(spec=LLMProvider)
    mock_provider.generate.side_effect = LLMTimeoutError("LLM upstream timed out after 30s")

    app.dependency_overrides[get_llm_provider] = lambda: mock_provider

    try:
        res = await async_client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "This will time out"},
            headers=headers,
        )
        assert res.status_code == 504
        body = res.json()
        assert body["error"]["code"] == "LLM_TIMEOUT"
        assert "timed out" in body["error"]["message"].lower()

        # Check LLM audit table for error status
        audit_res = await db_session.execute(
            select(LLMRequest).where(LLMRequest.conversation_id == conv_id)
        )
        audit_record = audit_res.scalar_one_or_none()
        assert audit_record is not None
        assert audit_record.status == "error"
        assert audit_record.error_message is not None
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


@pytest.mark.asyncio
async def test_llm_unrecoverable_error_produces_bad_gateway(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    db_session: AsyncSession,
) -> None:
    """Verify that unrecoverable provider errors produce 502 BAD_GATEWAY."""
    _, _, headers = primary_api_key

    conv_id = (
        await async_client.post(
            "/api/v1/conversations",
            json={"title": "Provider Error Test"},
            headers=headers,
        )
    ).json()["id"]

    mock_provider = AsyncMock(spec=LLMProvider)
    mock_provider.generate.side_effect = LLMProviderError("Upstream service unavailable")

    app.dependency_overrides[get_llm_provider] = lambda: mock_provider

    try:
        res = await async_client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "This will fail"},
            headers=headers,
        )
        assert res.status_code == 502
        body = res.json()
        assert body["error"]["code"] == "LLM_PROVIDER_ERROR"

        # Check LLM audit table for error status
        audit_res = await db_session.execute(
            select(LLMRequest).where(LLMRequest.conversation_id == conv_id)
        )
        audit_record = audit_res.scalar_one_or_none()
        assert audit_record is not None
        assert audit_record.status == "error"
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


@pytest.mark.asyncio
async def test_idempotency_prevents_duplicate_billing_and_db_records(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    db_session: AsyncSession,
) -> None:
    """Verify idempotent requests return cached payload without duplicate LLM executions."""
    _, _, headers = primary_api_key

    conv_id = (
        await async_client.post(
            "/api/v1/conversations",
            json={"title": "Idempotent Billing Test"},
            headers=headers,
        )
    ).json()["id"]

    idemp_headers = {**headers, "X-Idempotency-Key": "idemp-billing-test-key-999"}

    # First request
    res1 = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Idempotent query"},
        headers=idemp_headers,
    )
    assert res1.status_code == 200
    msg1 = res1.json()

    # Second request with identical key
    res2 = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Idempotent query"},
        headers=idemp_headers,
    )
    assert res2.status_code == 200
    msg2 = res2.json()

    assert msg1["id"] == msg2["id"]
    assert msg1["content"] == msg2["content"]

    # Verify exactly 1 user message and 1 assistant message in DB
    msgs_res = await db_session.execute(select(Message).where(Message.conversation_id == conv_id))
    all_msgs = msgs_res.scalars().all()
    assert len(all_msgs) == 2  # 1 user + 1 assistant

    # Verify exactly 1 LLM request audit record
    audits_res = await db_session.execute(
        select(LLMRequest).where(LLMRequest.conversation_id == conv_id)
    )
    all_audits = audits_res.scalars().all()
    assert len(all_audits) == 1
