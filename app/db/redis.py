"""Redis connection manager and dependency provider."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

if TYPE_CHECKING:
    RedisClient = Redis[str]
    RedisPool = ConnectionPool[Any]
else:
    RedisClient = Redis
    RedisPool = ConnectionPool


def get_redis_client() -> RedisClient:
    """Return a Redis client instance configured with settings."""
    return Redis.from_url(
        settings.redis_url,
        socket_timeout=settings.redis_socket_timeout_seconds,
        socket_connect_timeout=settings.redis_connect_timeout_seconds,
        decode_responses=True,
    )


async def get_redis() -> AsyncIterator[RedisClient]:
    """FastAPI dependency for obtaining a Redis client."""
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.close()


@asynccontextmanager
async def lifespan_redis() -> AsyncIterator[None]:
    """Lifespan context manager for Redis validation."""
    client = get_redis_client()
    try:
        await client.ping()
    finally:
        await client.close()
    yield
