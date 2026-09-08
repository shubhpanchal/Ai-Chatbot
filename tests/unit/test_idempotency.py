"""Unit tests for distributed Redis-backed idempotency service."""

from __future__ import annotations

import uuid

import pytest
from redis.asyncio import Redis

from app.core.exceptions import IdempotencyConflictError
from app.services.idempotency import IdempotencyService


@pytest.mark.asyncio
async def test_idempotency_lifecycle(redis_client: Redis[str]) -> None:
    """Verify lock acquisition, conflict detection, response storage, and cache retrieval."""
    service = IdempotencyService(
        redis=redis_client,
        lock_timeout_seconds=5,
        ttl_seconds=60,
    )
    api_key_id = uuid.uuid4()
    idem_key = "test-idem-uuid-001"

    # 1. First call acquires lock (returns None)
    cached = await service.acquire_or_get(api_key_id, idem_key)
    assert cached is None

    # 2. Concurrent call with same key encounters in-flight lock -> raises 409 Conflict
    with pytest.raises(IdempotencyConflictError):
        await service.acquire_or_get(api_key_id, idem_key)

    # 3. Execution finishes, response is cached
    response_payload = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": "Idempotent response",
        "usage": {"total_tokens": 42},
    }
    await service.store_response(api_key_id, idem_key, response_payload)

    # 4. Subsequent retry with same key returns cached response
    cached_after = await service.acquire_or_get(api_key_id, idem_key)
    assert cached_after is not None
    assert cached_after["id"] == response_payload["id"]
    assert cached_after["content"] == "Idempotent response"


@pytest.mark.asyncio
async def test_idempotency_release_lock_on_failure(redis_client: Redis[str]) -> None:
    """Verify releasing lock allows subsequent retry attempts."""
    service = IdempotencyService(
        redis=redis_client,
        lock_timeout_seconds=5,
        ttl_seconds=60,
    )
    api_key_id = uuid.uuid4()
    idem_key = "test-idem-failure-002"

    # Acquire lock
    assert await service.acquire_or_get(api_key_id, idem_key) is None

    # Release lock on failure
    await service.release_lock(api_key_id, idem_key)

    # Should be able to acquire lock again
    reacquired = await service.acquire_or_get(api_key_id, idem_key)
    assert reacquired is None
