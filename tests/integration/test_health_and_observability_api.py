"""Integration tests for health/readiness probes, request correlation, and metrics endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RedisClient, get_db, get_redis
from app.main import app
from app.models.api_key import APIKey


@pytest.mark.asyncio
async def test_liveness_health_probe(async_client: AsyncClient) -> None:
    """Verify that /health and /api/v1/health return 200 OK without pinging dependencies."""
    res1 = await async_client.get("/health")
    assert res1.status_code == 200
    body1 = res1.json()
    assert body1["status"] == "healthy"
    assert "timestamp" in body1

    res2 = await async_client.get("/api/v1/health")
    assert res2.status_code == 200
    assert res2.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_readiness_probe_healthy(async_client: AsyncClient) -> None:
    """Verify that /ready returns 200 OK with all checks connected when dependencies are healthy."""
    res = await async_client.get("/ready")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "connected"
    assert body["checks"]["redis"] == "connected"
    assert body["checks"]["llm_config"] == "valid"


@pytest.mark.asyncio
async def test_readiness_probe_postgres_failure(async_client: AsyncClient) -> None:
    """Verify that /ready returns 503 Service Unavailable when PostgreSQL is unreachable."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = ConnectionRefusedError("PostgreSQL connection refused")

    async def failing_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    app.dependency_overrides[get_db] = failing_get_db

    try:
        res = await async_client.get("/ready")
        assert res.status_code == 503
        body = res.json()
        assert body["status"] == "unready"
        assert body["checks"]["database"] == "unreachable"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_readiness_probe_redis_failure(async_client: AsyncClient) -> None:
    """Verify that /ready returns 503 Service Unavailable when Redis is unreachable."""
    mock_redis = AsyncMock(spec=RedisClient)
    mock_redis.ping.side_effect = ConnectionRefusedError("Redis connection refused")

    async def failing_get_redis() -> AsyncGenerator[RedisClient, None]:
        yield mock_redis

    app.dependency_overrides[get_redis] = failing_get_redis

    try:
        res = await async_client.get("/ready")
        assert res.status_code == 503
        body = res.json()
        assert body["status"] == "unready"
        assert body["checks"]["redis"] == "unreachable"
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_request_id_generation_and_propagation(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify request ID is generated/propagated in headers and error responses."""
    _, _, headers = primary_api_key

    # 1. Generated Request ID
    res1 = await async_client.get("/api/v1/conversations", headers=headers)
    assert res1.status_code == 200
    req_id1 = res1.headers.get("X-Request-ID")
    assert req_id1 is not None and len(req_id1) >= 10

    # 2. Propagated Custom Request ID
    custom_id = "test-custom-req-id-777"
    custom_headers = {**headers, "X-Request-ID": custom_id}
    res2 = await async_client.get("/api/v1/conversations", headers=custom_headers)
    assert res2.status_code == 200
    assert res2.headers.get("X-Request-ID") == custom_id

    # 3. Request ID in domain error response payload
    err_res = await async_client.get(
        "/api/v1/conversations/00000000-0000-0000-0000-000000000000",
        headers=custom_headers,
    )
    assert err_res.status_code == 404
    err_body = err_res.json()
    assert err_body["error"]["request_id"] == custom_id


@pytest.mark.asyncio
async def test_metrics_endpoint_snapshot(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify that /metrics endpoint returns the metrics snapshot dictionary."""
    _, _, headers = primary_api_key

    # Execute a request to generate metrics
    await async_client.get("/api/v1/conversations", headers=headers)

    res = await async_client.get("/metrics")
    assert res.status_code == 200
    body = res.json()

    assert "http" in body
    assert "llm" in body
    assert "infrastructure" in body
    assert "application" in body
    assert len(body["http"]["requests"]) >= 1
