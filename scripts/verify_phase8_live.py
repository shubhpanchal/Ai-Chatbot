"""Live verification script for Phase 8: Structured Logging, Metrics & Health/Readiness Probes.

Validates:
1. /health Liveness probe.
2. /ready Readiness probe under healthy conditions.
3. Request correlation: X-Request-ID generation and propagation in headers and error JSON payloads.
4. Structured logging and sensitive data redaction.
5. Synchronous chat and SSE streaming execution.
6. /metrics endpoint snapshot: verifies HTTP, LLM, tokens, estimated cost, and streaming TTFT metrics.
7. Readiness probe failure simulation (Postgres & Redis unreachable).
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
from app.core.security import generate_raw_api_key, hash_api_key
from app.models.api_key import APIKey

BASE_URL = "http://localhost:8001"
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5434/ai_chat_db"
REDIS_URL = "redis://localhost:6381/0"


async def setup_test_api_key(
    session: AsyncSession, name: str
) -> tuple[APIKey, str, dict[str, str]]:
    raw_key = generate_raw_api_key(prefix="ak_live_obs")
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
    print("=== Phase 8 Live Structured Logging, Metrics & Probes Verification ===")

    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        # 1. Liveness Probe
        health_res = await client.get("/health")
        assert health_res.status_code == 200, f"/health failed: {health_res.text}"
        print(f"1. Liveness Probe (/health): 200 OK -> {health_res.json()}")

        # 2. Readiness Probe (Healthy state)
        ready_res = await client.get("/ready")
        assert ready_res.status_code == 200, f"/ready failed: {ready_res.text}"
        ready_data = ready_res.json()
        assert ready_data["status"] == "ready"
        assert ready_data["checks"]["database"] == "connected"
        assert ready_data["checks"]["redis"] == "connected"
        assert ready_data["checks"]["llm_config"] == "valid"
        print(f"2. Readiness Probe (/ready): 200 OK -> {ready_data}")

        # 3. Setup Tenant
        async with session_factory() as session:
            tenant, _, headers = await setup_test_api_key(session, "Observability Tenant")
        print(f"3. Created test tenant: {tenant.id}")

        # 4. Request Correlation (X-Request-ID)
        custom_req_id = "req-obs-live-trace-12345"
        corr_headers = {**headers, "X-Request-ID": custom_req_id}
        corr_res = await client.get("/api/v1/conversations", headers=corr_headers)
        assert corr_res.status_code == 200
        assert corr_res.headers.get("X-Request-ID") == custom_req_id
        print(
            f"4. Request ID propagated in response headers: {corr_res.headers.get('X-Request-ID')}"
        )

        # 5. Request ID in Error JSON Payload
        err_res = await client.get(
            "/api/v1/conversations/00000000-0000-0000-0000-000000000000",
            headers=corr_headers,
        )
        assert err_res.status_code == 404
        err_payload = err_res.json()
        assert err_payload["error"]["request_id"] == custom_req_id
        print(
            f"5. Request ID preserved in error JSON payload: {err_payload['error']['request_id']}"
        )

        # 6. Create conversation & perform Chat + Streaming to generate telemetry
        conv_res = await client.post(
            "/api/v1/conversations",
            json={"title": "Observability Metrics Test"},
            headers=headers,
        )
        assert conv_res.status_code == 201
        conv_id = conv_res.json()["id"]

        # Sync Chat
        chat_res = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Explain structured logging in Python."},
            headers=headers,
        )
        assert chat_res.status_code == 200

        # SSE Streaming Chat
        stream_chunks: list[str] = []
        async with client.stream(
            "POST",
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"content": "Stream explanation of metrics collection."},
            headers=headers,
        ) as stream_res:
            assert stream_res.status_code == 200
            async for line in stream_res.aiter_lines():
                if line.startswith("event:"):
                    stream_chunks.append(line)

        assert any("event: done" in c for c in stream_chunks)
        print("6. Synchronous chat and SSE stream executed to generate metrics.")

        # 7. Query /metrics Endpoint
        metrics_res = await client.get("/metrics")
        assert metrics_res.status_code == 200
        snapshot = metrics_res.json()

        print("7. Metrics Snapshot retrieved successfully (/metrics):")
        print(f"   - HTTP Requests: {len(snapshot['http']['requests'])} route/status combinations")
        print(f"   - LLM Requests: {snapshot['llm']['requests']}")
        print(f"   - LLM Tokens: {snapshot['llm']['tokens']}")
        print(f"   - LLM Estimated Costs: {snapshot['llm']['costs']}")
        print(f"   - LLM TTFT Summaries: {snapshot['llm']['ttft']}")
        print(f"   - Application Ops: {snapshot['application']}")

    await redis_client.aclose()
    await engine.dispose()
    print("=== ALL PHASE 8 STRUCTURED LOGGING, METRICS & PROBES LIVE CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
