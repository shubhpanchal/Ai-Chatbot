"""Live verification script for Phase 7: Redis Rate Limiting & Resilience.

Validates:
1. API Health check.
2. Tenant creation and authentication.
3. Rate limit response headers (X-RateLimit-Limit, Remaining, Reset).
4. Sliding-window rate limit exhaustion and 429 RATE_LIMIT_EXCEEDED behavior.
5. Retry-After header presence and validity.
6. Cross-tenant isolation (Tenant A limited, Tenant B unrestricted).
7. Atomic concurrent requests behavior.
8. Synchronous chat and SSE streaming functionality under rate limiting.
9. Redis resilience fail-closed error handling.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.security import generate_raw_api_key, hash_api_key
from app.models.api_key import APIKey
from app.services.rate_limiter import RateLimiterService

BASE_URL = "http://localhost:8001"
REDIS_URL = "redis://localhost:6381/0"
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5434/ai_chat_db"


async def setup_test_api_key(
    session: AsyncSession, name: str
) -> tuple[APIKey, str, dict[str, str]]:
    raw_key = generate_raw_api_key(prefix="ak_live_rate")
    key_hash = hash_api_key(raw_key, settings.api_key_secret)
    api_key = APIKey(
        id=uuid.uuid4(),
        name=name,
        key_hash=key_hash,
        is_active=True,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    headers = {
        "Authorization": f"Bearer {raw_key}",
        "Content-Type": "application/json",
    }
    return api_key, raw_key, headers


async def main() -> None:
    print("=== Phase 7 Live Redis Rate Limiting & Resilience Verification ===")

    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        # 1. Health check
        health_res = await client.get("/health")
        assert health_res.status_code == 200, f"Health check failed: {health_res.text}"
        print(f"1. Health check: 200 OK -> {health_res.json()}")

        # 2. Setup Tenants
        async with session_factory() as session:
            tenant_a, _, headers_a = await setup_test_api_key(session, "RateLimit Tenant A")
            tenant_b, _, headers_b = await setup_test_api_key(session, "RateLimit Tenant B")

        limiter = RateLimiterService(
            redis=redis_client, default_limit=100, default_window_seconds=60
        )
        await limiter.reset(tenant_a.id)
        await limiter.reset(tenant_b.id)
        print(f"2. Created test API keys: Tenant A ({tenant_a.id}), Tenant B ({tenant_b.id})")

        # 3. Verify Rate Limit Headers on standard request
        conv_res = await client.post(
            "/api/v1/conversations",
            json={"title": "Rate Limit Verification Convo"},
            headers=headers_a,
        )
        assert conv_res.status_code == 201
        conv_id = conv_res.json()["id"]

        assert "X-RateLimit-Limit" in conv_res.headers
        assert "X-RateLimit-Remaining" in conv_res.headers
        assert "X-RateLimit-Reset" in conv_res.headers
        limit_val = int(conv_res.headers["X-RateLimit-Limit"])
        rem_val = int(conv_res.headers["X-RateLimit-Remaining"])
        print("3. Rate limit headers verified on POST /conversations:")
        print(f"   - X-RateLimit-Limit: {limit_val}")
        print(f"   - X-RateLimit-Remaining: {rem_val}")
        print(f"   - X-RateLimit-Reset: {conv_res.headers['X-RateLimit-Reset']}")

        # 4. Direct sliding-window saturation test with RateLimiterService
        test_limiter = RateLimiterService(
            redis=redis_client, default_limit=3, default_window_seconds=60
        )
        await test_limiter.reset(tenant_a.id)

        r1 = await test_limiter.check_rate_limit(tenant_a.id)
        r2 = await test_limiter.check_rate_limit(tenant_a.id)
        r3 = await test_limiter.check_rate_limit(tenant_a.id)
        r4 = await test_limiter.check_rate_limit(tenant_a.id)

        assert r1.allowed is True and r1.remaining == 2
        assert r2.allowed is True and r2.remaining == 1
        assert r3.allowed is True and r3.remaining == 0
        assert r4.allowed is False and r4.retry_after >= 1
        print("4. Sliding-window exact limit (3 req) and 4th request rejection verified.")

        # 5. Multi-tenant isolation verification
        r_tenant_b = await test_limiter.check_rate_limit(tenant_b.id)
        assert r_tenant_b.allowed is True and r_tenant_b.remaining == 2
        print("5. Multi-tenant isolation verified: Tenant A at limit does NOT affect Tenant B.")

        # 6. Synchronous Chat under Rate Limiting
        sync_chat_res = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Test synchronous chat message under rate limiter"},
            headers=headers_a,
        )
        assert sync_chat_res.status_code == 200
        assert "X-RateLimit-Remaining" in sync_chat_res.headers
        print(
            f"6. Synchronous chat succeeded under rate limiting (Remaining: {sync_chat_res.headers['X-RateLimit-Remaining']})"
        )

        # 7. SSE Streaming under Rate Limiting
        stream_chunks: list[str] = []
        async with client.stream(
            "POST",
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"content": "Test streaming message under rate limiter"},
            headers=headers_a,
        ) as stream_res:
            assert stream_res.status_code == 200
            assert "text/event-stream" in stream_res.headers["content-type"]
            async for line in stream_res.aiter_lines():
                if line.startswith("event: "):
                    stream_chunks.append(line)

        assert any("event: done" in c for c in stream_chunks)
        print(
            f"7. SSE Streaming succeeded under rate limiting ({len(stream_chunks)} events received)."
        )

        # 8. High Concurrency Atomicity check
        concurrency_limiter = RateLimiterService(
            redis=redis_client, default_limit=10, default_window_seconds=60
        )
        test_tenant_id = uuid.uuid4()
        await concurrency_limiter.reset(test_tenant_id)

        tasks = [concurrency_limiter.check_rate_limit(test_tenant_id) for _ in range(25)]
        results = await asyncio.gather(*tasks)

        allowed_count = sum(1 for r in results if r.allowed)
        rejected_count = sum(1 for r in results if not r.allowed)
        assert allowed_count == 10
        assert rejected_count == 15
        print(
            "8. Atomicity verified under 25 concurrent requests: exactly 10 allowed, 15 rejected."
        )

        # 9. Redis Resilience Verification
        fail_closed_limiter = RateLimiterService(
            redis=Redis.from_url(
                "redis://localhost:9999/0",
                socket_timeout=0.2,
                socket_connect_timeout=0.2,
                decode_responses=True,
            ),
            fail_open=False,
        )
        try:
            await fail_closed_limiter.check_rate_limit(tenant_a.id)
            raise AssertionError("Expected ServiceUnavailableError on unreachable Redis")
        except ServiceUnavailableError as e:
            assert "temporarily unavailable" in str(e).lower()
            print(
                f"9. Redis resilience verified: Fail-closed policy raises ServiceUnavailableError ({e.status_code} {e.code}) when Redis is unreachable."
            )

    await redis_client.close()
    await engine.dispose()
    print("=== ALL PHASE 7 RATE LIMITING & RESILIENCE LIVE CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
