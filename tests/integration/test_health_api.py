"""Integration tests for health and liveness probe endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient) -> None:
    """Test root endpoint returns service metadata."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "AI Chat API"
    assert "version" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient) -> None:
    """Test /health liveness probe returns healthy status and timestamp."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_api_v1_health_endpoint(async_client: AsyncClient) -> None:
    """Test /api/v1/health endpoint returns healthy status and timestamp."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
