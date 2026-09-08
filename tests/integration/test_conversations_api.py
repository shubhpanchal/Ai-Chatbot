"""Integration tests for conversation CRUD endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from app.models.api_key import APIKey


@pytest.mark.asyncio
async def test_create_conversation_success(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify POST /api/v1/conversations successfully creates a conversation thread."""
    _, _, headers = primary_api_key
    payload = {
        "title": "Async Python Mastery",
        "system_prompt": "You are a senior Python concurrency architect.",
    }

    response = await async_client.post(
        "/api/v1/conversations",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert uuid.UUID(data["id"])
    assert data["title"] == "Async Python Mastery"
    assert data["system_prompt"] == "You are a senior Python concurrency architect."
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_conversation_validation_error(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify POST /api/v1/conversations rejects invalid payloads with standard 422 error."""
    _, _, headers = primary_api_key

    # Missing title
    res_missing = await async_client.post(
        "/api/v1/conversations",
        json={"system_prompt": "Prompt without title"},
        headers=headers,
    )
    assert res_missing.status_code == 422
    data_missing = res_missing.json()
    assert data_missing["error"]["code"] == "VALIDATION_ERROR"

    # Extra unpermitted fields (forbid extra)
    res_extra = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Test", "unknown_field": "disallowed"},
        headers=headers,
    )
    assert res_extra.status_code == 422
    data_extra = res_extra.json()
    assert data_extra["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_list_conversations_pagination_and_ordering(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify GET /api/v1/conversations pagination and newest-first ordering."""
    _, _, headers = primary_api_key

    created_ids: list[str] = []
    for i in range(5):
        res = await async_client.post(
            "/api/v1/conversations",
            json={"title": f"Thread {i}"},
            headers=headers,
        )
        assert res.status_code == 201
        created_ids.append(res.json()["id"])

    # Page 1, size 2
    res_page1 = await async_client.get(
        "/api/v1/conversations?page=1&page_size=2",
        headers=headers,
    )
    assert res_page1.status_code == 200
    p1 = res_page1.json()
    assert p1["page"] == 1
    assert p1["page_size"] == 2
    assert p1["total"] >= 5
    assert len(p1["items"]) == 2
    # Newest thread (Thread 4) should be first
    assert p1["items"][0]["id"] == created_ids[-1]

    # Page 2, size 2
    res_page2 = await async_client.get(
        "/api/v1/conversations?page=2&page_size=2",
        headers=headers,
    )
    assert res_page2.status_code == 200
    p2 = res_page2.json()
    assert p2["page"] == 2
    assert len(p2["items"]) == 2
    # Should not overlap with page 1
    p1_ids = {item["id"] for item in p1["items"]}
    p2_ids = {item["id"] for item in p2["items"]}
    assert p1_ids.isdisjoint(p2_ids)


@pytest.mark.asyncio
async def test_get_conversation_detail_and_stats(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify GET /api/v1/conversations/{id} returns full detail and usage stats."""
    _, _, headers = primary_api_key

    # Create thread
    res_create = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Detail Test", "system_prompt": "Helpful bot"},
        headers=headers,
    )
    conv_id = res_create.json()["id"]

    # Retrieve detail
    res_get = await async_client.get(
        f"/api/v1/conversations/{conv_id}",
        headers=headers,
    )
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["id"] == conv_id
    assert data["title"] == "Detail Test"
    assert data["system_prompt"] == "Helpful bot"
    assert "messages" in data
    assert isinstance(data["messages"], list)
    assert "usage_summary" in data
    assert data["usage_summary"]["total_requests"] == 0
    assert data["usage_summary"]["total_tokens"] == 0
    assert data["usage_summary"]["estimated_cost_usd"] == 0.0


@pytest.mark.asyncio
async def test_conversation_soft_delete_lifecycle(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify DELETE /api/v1/conversations/{id} soft-deletes and excludes from subsequent operations."""
    _, _, headers = primary_api_key

    # Create thread
    res_create = await async_client.post(
        "/api/v1/conversations",
        json={"title": "To Be Deleted"},
        headers=headers,
    )
    conv_id = res_create.json()["id"]

    # Delete thread
    res_del = await async_client.delete(
        f"/api/v1/conversations/{conv_id}",
        headers=headers,
    )
    assert res_del.status_code == 204
    assert res_del.content == b""

    # Attempt to GET deleted thread -> 404 CONVERSATION_NOT_FOUND
    res_get = await async_client.get(
        f"/api/v1/conversations/{conv_id}",
        headers=headers,
    )
    assert res_get.status_code == 404
    assert res_get.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"

    # Attempt to DELETE already deleted thread -> 404 CONVERSATION_NOT_FOUND
    res_del2 = await async_client.delete(
        f"/api/v1/conversations/{conv_id}",
        headers=headers,
    )
    assert res_del2.status_code == 404
    assert res_del2.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"

    # Verify deleted thread is excluded from list
    res_list = await async_client.get(
        "/api/v1/conversations?page=1&page_size=100",
        headers=headers,
    )
    assert res_list.status_code == 200
    listed_ids = [item["id"] for item in res_list.json()["items"]]
    assert conv_id not in listed_ids
