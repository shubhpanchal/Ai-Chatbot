"""Unit tests for distributed Redis-backed sliding-window rate limiter."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.exceptions import ServiceUnavailableError
from app.services.rate_limiter import RateLimiterService


@pytest.mark.asyncio
async def test_rate_limiter_sliding_window_normal(redis_client: Redis[str]) -> None:
    """Verify normal rate limiter usage decrements remaining requests within the sliding window."""
    limiter = RateLimiterService(redis=redis_client, default_limit=5, default_window_seconds=60)
    api_key_id = uuid.uuid4()
    await limiter.reset(api_key_id)

    # Make 3 calls within a limit of 5
    res1 = await limiter.check_rate_limit(api_key_id)
    assert res1.allowed is True
    assert res1.limit == 5
    assert res1.remaining == 4
    assert res1.retry_after == 0

    res2 = await limiter.check_rate_limit(api_key_id)
    assert res2.allowed is True
    assert res2.remaining == 3

    res3 = await limiter.check_rate_limit(api_key_id)
    assert res3.allowed is True
    assert res3.remaining == 2


@pytest.mark.asyncio
async def test_rate_limiter_exact_limit_and_exceeded(redis_client: Redis[str]) -> None:
    """Verify exact-at-limit and exceeded limit return appropriate metadata and retry_after."""
    limiter = RateLimiterService(redis=redis_client, default_limit=3, default_window_seconds=60)
    api_key_id = uuid.uuid4()
    await limiter.reset(api_key_id)

    # 1. First request
    r1 = await limiter.check_rate_limit(api_key_id)
    assert r1.allowed is True
    assert r1.remaining == 2

    # 2. Second request
    r2 = await limiter.check_rate_limit(api_key_id)
    assert r2.allowed is True
    assert r2.remaining == 1

    # 3. Third request (exactly at limit)
    r3 = await limiter.check_rate_limit(api_key_id)
    assert r3.allowed is True
    assert r3.remaining == 0

    # 4. Fourth request (exceeded limit)
    r4 = await limiter.check_rate_limit(api_key_id)
    assert r4.allowed is False
    assert r4.remaining == 0
    assert r4.retry_after >= 1


@pytest.mark.asyncio
async def test_rate_limiter_window_eviction(redis_client: Redis[str]) -> None:
    """Verify expired entries roll out of the sliding window after the window duration passes."""
    limiter = RateLimiterService(redis=redis_client, default_limit=2, default_window_seconds=1)
    api_key_id = uuid.uuid4()
    await limiter.reset(api_key_id)

    # Exhaust limit of 2 in a 1-second window
    r1 = await limiter.check_rate_limit(api_key_id)
    r2 = await limiter.check_rate_limit(api_key_id)
    r3 = await limiter.check_rate_limit(api_key_id)
    assert r1.allowed is True
    assert r2.allowed is True
    assert r3.allowed is False

    # Wait for the 1-second window to expire
    await asyncio.sleep(1.1)

    # Next request should be admitted
    r4 = await limiter.check_rate_limit(api_key_id)
    assert r4.allowed is True
    assert r4.remaining == 1


@pytest.mark.asyncio
async def test_rate_limiter_multi_tenant_isolation(redis_client: Redis[str]) -> None:
    """Verify each tenant API key has a strictly isolated sliding window."""
    limiter = RateLimiterService(redis=redis_client, default_limit=2, default_window_seconds=60)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await limiter.reset(tenant_a)
    await limiter.reset(tenant_b)

    # Tenant A exhausts its quota
    assert (await limiter.check_rate_limit(tenant_a)).allowed is True
    assert (await limiter.check_rate_limit(tenant_a)).allowed is True
    assert (await limiter.check_rate_limit(tenant_a)).allowed is False

    # Tenant B is completely unblocked
    r_b = await limiter.check_rate_limit(tenant_b)
    assert r_b.allowed is True
    assert r_b.remaining == 1


@pytest.mark.asyncio
async def test_rate_limiter_redis_resilience_fail_closed() -> None:
    """Verify that when Redis is unreachable, fail-closed policy raises ServiceUnavailableError."""
    mock_redis = AsyncMock(spec=Redis)
    mock_redis.eval.side_effect = RedisConnectionError("Connection refused by Redis")

    limiter = RateLimiterService(redis=mock_redis, fail_open=False)
    api_key_id = uuid.uuid4()

    with pytest.raises(ServiceUnavailableError) as exc_info:
        await limiter.check_rate_limit(api_key_id)

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_rate_limiter_redis_resilience_fail_open() -> None:
    """Verify that when fail_open=True, Redis errors fail open gracefully."""
    mock_redis = AsyncMock(spec=Redis)
    mock_redis.eval.side_effect = RedisConnectionError("Connection timeout")

    limiter = RateLimiterService(redis=mock_redis, fail_open=True)
    api_key_id = uuid.uuid4()

    result = await limiter.check_rate_limit(api_key_id)
    assert result.allowed is True
    assert result.remaining == 1
