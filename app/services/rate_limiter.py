"""Redis-backed distributed sliding-window rate limiter service."""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError

if TYPE_CHECKING:
    RedisClient = Redis[str]
else:
    RedisClient = Redis

logger = logging.getLogger(__name__)

# Atomic sliding-window rate limiter Lua script using Redis server TIME
SLIDING_WINDOW_LUA_SCRIPT = """
local key = KEYS[1]
local window_ms = tonumber(ARGV[1])
local max_limit = tonumber(ARGV[2])
local req_id = ARGV[3]

-- 1. Get Redis server time in milliseconds
local time_res = redis.call('TIME')
local now_sec = tonumber(time_res[1])
local now_usec = tonumber(time_res[2])
local now_ms = (now_sec * 1000) + math.floor(now_usec / 1000)

-- 2. Evict expired entries outside the sliding window
local clear_before = now_ms - window_ms
redis.call('ZREMRANGEBYSCORE', key, 0, clear_before)

-- 3. Count active entries in current window
local current_count = redis.call('ZCARD', key)

-- 4. Check if limit is reached
if current_count < max_limit then
    local member = tostring(now_ms) .. ':' .. req_id
    redis.call('ZADD', key, now_ms, member)
    redis.call('PEXPIRE', key, window_ms)

    local remaining = max_limit - current_count - 1
    local reset_epoch = now_sec + math.ceil(window_ms / 1000)
    return {1, remaining, reset_epoch, 0}
else
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 1
    local reset_epoch = now_sec + math.ceil(window_ms / 1000)

    if oldest and #oldest >= 2 then
        local oldest_score = tonumber(oldest[2])
        local expire_at_ms = oldest_score + window_ms
        local wait_ms = expire_at_ms - now_ms
        if wait_ms > 0 then
            retry_after = math.ceil(wait_ms / 1000)
            reset_epoch = math.ceil(expire_at_ms / 1000)
        end
    end

    return {0, 0, reset_epoch, retry_after}
end
"""


@dataclass(frozen=True)
class RateLimitResult:
    """Result metadata for a sliding-window rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_epoch: int
    retry_after: int


class RateLimiterService:
    """Distributed sliding-window rate limiter using Redis sorted sets (ZSET)."""

    def __init__(
        self,
        redis: RedisClient,
        default_limit: int | None = None,
        default_window_seconds: int | None = None,
        fail_open: bool | None = None,
    ) -> None:
        self.redis = redis
        self.default_limit = default_limit or settings.rate_limit_requests
        self.default_window_seconds = default_window_seconds or settings.rate_limit_window_seconds
        self.fail_open = fail_open if fail_open is not None else settings.rate_limit_fail_open

    def _build_key(self, api_key_id: uuid.UUID) -> str:
        """Construct isolated Redis key per tenant API key."""
        return f"ratelimit:{api_key_id}"

    async def check_rate_limit(
        self,
        api_key_id: uuid.UUID,
        limit: int | None = None,
        window_seconds: int | None = None,
    ) -> RateLimitResult:
        """Execute atomic sliding-window rate limit evaluation.

        Args:
            api_key_id: Authenticated tenant API key ID.
            limit: Maximum requests allowed within window (defaults to config).
            window_seconds: Sliding window duration in seconds (defaults to config).

        Returns:
            RateLimitResult indicating whether request is allowed and rate limit metadata.

        Raises:
            ServiceUnavailableError: When Redis is unreachable and fail_open is False.
        """
        max_limit = limit if limit is not None else self.default_limit
        window_sec = window_seconds if window_seconds is not None else self.default_window_seconds
        window_ms = window_sec * 1000
        key = self._build_key(api_key_id)
        req_id = str(uuid.uuid4())

        try:
            # Execute atomic Lua script with Redis socket timeout boundary
            result: Any = await self.redis.eval(  # type: ignore[no-untyped-call]
                SLIDING_WINDOW_LUA_SCRIPT,
                1,
                key,
                str(window_ms),
                str(max_limit),
                req_id,
            )

            # Lua script returns [allowed (0/1), remaining, reset_epoch, retry_after]
            allowed_flag = bool(result[0] == 1)
            remaining = int(result[1])
            reset_epoch = int(result[2])
            retry_after = int(result[3])

            return RateLimitResult(
                allowed=allowed_flag,
                limit=max_limit,
                remaining=remaining,
                reset_epoch=reset_epoch,
                retry_after=retry_after,
            )

        except (RedisError, TimeoutError, OSError) as exc:
            logger.error(
                "Redis rate limiter encounter error (fail_open=%s): %s",
                self.fail_open,
                exc,
                exc_info=True,
            )
            if self.fail_open:
                # Permissive fallback if configured
                now_epoch = int(time.time())
                return RateLimitResult(
                    allowed=True,
                    limit=max_limit,
                    remaining=1,
                    reset_epoch=now_epoch + window_sec,
                    retry_after=0,
                )
            # Default secure fail-closed posture
            raise ServiceUnavailableError(
                message="Rate limiting service temporarily unavailable.",
                details={"service": "redis", "reason": "rate_limiter_unreachable"},
            ) from exc

    async def reset(self, api_key_id: uuid.UUID) -> None:
        """Clear rate limit history for a specific API key (useful for tests/admin)."""
        key = self._build_key(api_key_id)
        try:
            await self.redis.delete(key)
        except Exception as exc:
            logger.warning("Failed to reset rate limit key %s: %s", key, exc)
