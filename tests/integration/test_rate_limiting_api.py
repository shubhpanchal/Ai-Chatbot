"""Integration tests for Redis-backed sliding-window rate limiting on API endpoints."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.api.deps import get_rate_limiter
from app.main import app
from app.models.api_key import APIKey
from app.services.rate_limiter import RateLimiterService

if TYPE_CHECKING:
    pass


@pytest.mark.asyncio
async def test_rate_limit_headers_on_successful_request(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    redis_client: Redis[str],
) -> None:
    """Verify rate limit headers (X-RateLimit-Limit, Remaining, Reset) are attached to responses."""
    api_key, _, headers = primary_api_key
    limiter = RateLimiterService(redis=redis_client, default_limit=100, default_window_seconds=60)
    await limiter.reset(api_key.id)

    res = await async_client.get("/api/v1/conversations", headers=headers)
    assert res.status_code == 200

    assert "X-RateLimit-Limit" in res.headers
    assert "X-RateLimit-Remaining" in res.headers
    assert "X-RateLimit-Reset" in res.headers
    assert int(res.headers["X-RateLimit-Limit"]) == 100
    assert int(res.headers["X-RateLimit-Remaining"]) < 100


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    redis_client: Redis[str],
) -> None:
    """Verify exceeding the rate limit returns 429 RATE_LIMIT_EXCEEDED with Retry-After header."""
    api_key, _, headers = primary_api_key

    # Configure a restrictive rate limiter (2 requests / 60 seconds)
    custom_limiter = RateLimiterService(
        redis=redis_client,
        default_limit=2,
        default_window_seconds=60,
    )
    await custom_limiter.reset(api_key.id)
    app.dependency_overrides[get_rate_limiter] = lambda: custom_limiter

    try:
        # Request 1: OK
        res1 = await async_client.get("/api/v1/conversations", headers=headers)
        assert res1.status_code == 200
        assert res1.headers["X-RateLimit-Remaining"] == "1"

        # Request 2: OK (at limit)
        res2 = await async_client.get("/api/v1/conversations", headers=headers)
        assert res2.status_code == 200
        assert res2.headers["X-RateLimit-Remaining"] == "0"

        # Request 3: 429 RATE_LIMIT_EXCEEDED
        res3 = await async_client.get("/api/v1/conversations", headers=headers)
        assert res3.status_code == 429
        assert "Retry-After" in res3.headers
        assert int(res3.headers["Retry-After"]) >= 1

        body = res3.json()
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "Rate limit exceeded" in body["error"]["message"]
        assert body["error"]["details"]["limit"] == 2
        assert body["error"]["details"]["window_seconds"] == 60
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)


@pytest.mark.asyncio
async def test_rate_limit_multi_tenant_isolation_api(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    secondary_api_key: tuple[APIKey, str, dict[str, str]],
    redis_client: Redis[str],
) -> None:
    """Verify that Tenant A hitting rate limits has zero impact on Tenant B."""
    tenant_a, _, headers_a = primary_api_key
    tenant_b, _, headers_b = secondary_api_key

    custom_limiter = RateLimiterService(
        redis=redis_client,
        default_limit=1,
        default_window_seconds=60,
    )
    await custom_limiter.reset(tenant_a.id)
    await custom_limiter.reset(tenant_b.id)
    app.dependency_overrides[get_rate_limiter] = lambda: custom_limiter

    try:
        # Tenant A request 1 -> OK
        res_a1 = await async_client.get("/api/v1/conversations", headers=headers_a)
        assert res_a1.status_code == 200

        # Tenant A request 2 -> 429
        res_a2 = await async_client.get("/api/v1/conversations", headers=headers_a)
        assert res_a2.status_code == 429

        # Tenant B request 1 -> OK (Tenant B is completely unblocked)
        res_b1 = await async_client.get("/api/v1/conversations", headers=headers_b)
        assert res_b1.status_code == 200
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)


@pytest.mark.asyncio
async def test_rate_limit_concurrent_requests_atomicity(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    redis_client: Redis[str],
) -> None:
    """Verify atomic Lua execution under high concurrency: exactly limit requests succeed."""
    api_key, _, headers = primary_api_key

    limit = 5
    custom_limiter = RateLimiterService(
        redis=redis_client,
        default_limit=limit,
        default_window_seconds=60,
    )
    await custom_limiter.reset(api_key.id)
    app.dependency_overrides[get_rate_limiter] = lambda: custom_limiter

    try:
        # Send 12 concurrent requests simultaneously
        tasks = [async_client.get("/api/v1/conversations", headers=headers) for _ in range(12)]
        responses = await asyncio.gather(*tasks)

        ok_count = sum(1 for r in responses if r.status_code == 200)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)

        assert ok_count == limit
        assert rate_limited_count == 12 - limit
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)


@pytest.mark.asyncio
async def test_rate_limit_streaming_endpoint_enforcement(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    redis_client: Redis[str],
) -> None:
    """Verify that the SSE streaming endpoint enforces rate limits and returns 429 JSON if exceeded."""
    api_key, _, headers = primary_api_key

    # 1. Create a conversation first
    conv_res = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Streaming Rate Limit Test"},
        headers=headers,
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # 2. Limit to 1 request
    custom_limiter = RateLimiterService(
        redis=redis_client,
        default_limit=1,
        default_window_seconds=60,
    )
    await custom_limiter.reset(api_key.id)
    app.dependency_overrides[get_rate_limiter] = lambda: custom_limiter

    try:
        # 1st streaming call: Admitted (200 OK text/event-stream)
        stream_res1 = await async_client.post(
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"content": "Stream turn 1"},
            headers=headers,
        )
        assert stream_res1.status_code == 200
        assert "text/event-stream" in stream_res1.headers["content-type"]

        # 2nd streaming call: Exceeded -> Returns 429 JSON response before stream begins
        stream_res2 = await async_client.post(
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"content": "Stream turn 2"},
            headers=headers,
        )
        assert stream_res2.status_code == 429
        body = stream_res2.json()
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)


@pytest.mark.asyncio
async def test_rate_limit_redis_failure_resilience_api(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify that when Redis is unreachable, fail-closed policy returns 503 SERVICE_UNAVAILABLE."""
    _, _, headers = primary_api_key

    mock_redis = AsyncMock(spec=Redis)
    mock_redis.eval.side_effect = RedisConnectionError("Redis cluster unreachable")
    failing_limiter = RateLimiterService(redis=mock_redis, fail_open=False)
    app.dependency_overrides[get_rate_limiter] = lambda: failing_limiter

    try:
        res = await async_client.get("/api/v1/conversations", headers=headers)
        assert res.status_code == 503
        body = res.json()
        assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert "Rate limiting service temporarily unavailable" in body["error"]["message"]
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)
