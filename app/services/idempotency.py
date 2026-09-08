"""Distributed idempotency service backed by Redis."""

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis

from app.core.config import settings
from app.core.exceptions import IdempotencyConflictError

if TYPE_CHECKING:
    RedisClient = Redis[str]
else:
    RedisClient = Redis

logger = logging.getLogger(__name__)


class IdempotencyService:
    """Manages idempotent request locking and response caching via Redis."""

    def __init__(
        self,
        redis: RedisClient,
        lock_timeout_seconds: int | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        self.redis = redis
        self.lock_timeout = lock_timeout_seconds or settings.idempotency_lock_timeout_seconds
        self.ttl_seconds = ttl_seconds or settings.idempotency_ttl_seconds

    def _format_key(self, api_key_id: uuid.UUID, idempotency_key: str) -> str:
        """Format namespaced Redis key for tenant idempotency tracking."""
        return f"idempotency:{api_key_id}:{idempotency_key.strip()}"

    async def acquire_or_get(
        self,
        api_key_id: uuid.UUID,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        """Check for existing response or acquire an atomic in-flight processing lock.

        Returns:
            dict: Cached response payload if previously completed.
            None: If lock was acquired successfully and execution should proceed.

        Raises:
            IdempotencyConflictError: If request with this key is currently in-flight.
        """
        redis_key = self._format_key(api_key_id, idempotency_key)

        existing = await self.redis.get(redis_key)
        if existing:
            try:
                data = json.loads(existing)
                status = data.get("status")
                if status == "processing":
                    raise IdempotencyConflictError(
                        "A request with this Idempotency-Key is currently in progress."
                    )
                if status == "completed":
                    logger.info("Idempotency cache hit for key %s", idempotency_key)
                    return data.get("response")  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                logger.warning("Corrupted idempotency entry found for %s; clearing.", redis_key)
                await self.redis.delete(redis_key)

        # Attempt atomic lock acquisition (NX = set only if not exists)
        lock_payload = json.dumps({"status": "processing"})
        acquired = await self.redis.set(
            redis_key,
            lock_payload,
            nx=True,
            ex=self.lock_timeout,
        )
        if not acquired:
            raise IdempotencyConflictError(
                "A request with this Idempotency-Key is currently in progress."
            )

        return None

    async def store_response(
        self,
        api_key_id: uuid.UUID,
        idempotency_key: str,
        response: dict[str, Any],
    ) -> None:
        """Cache completed response payload with 24-hour TTL."""
        redis_key = self._format_key(api_key_id, idempotency_key)
        payload = json.dumps({"status": "completed", "response": response})
        await self.redis.set(redis_key, payload, ex=self.ttl_seconds)

    async def release_lock(
        self,
        api_key_id: uuid.UUID,
        idempotency_key: str,
    ) -> None:
        """Release in-flight processing lock upon failure so client retries can proceed."""
        redis_key = self._format_key(api_key_id, idempotency_key)
        existing = await self.redis.get(redis_key)
        if existing:
            try:
                data = json.loads(existing)
                if data.get("status") == "processing":
                    await self.redis.delete(redis_key)
            except json.JSONDecodeError:
                await self.redis.delete(redis_key)
