"""Integration tests for HMAC authentication and cross-tenant isolation."""

import pytest
from httpx import AsyncClient

from app.models.api_key import APIKey


@pytest.mark.asyncio
async def test_auth_missing_header(async_client: AsyncClient) -> None:
    """Verify endpoints reject requests lacking Authorization header with 401 UNAUTHORIZED."""
    response = await async_client.get("/api/v1/conversations")
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "Missing or invalid" in data["error"]["message"]


@pytest.mark.asyncio
async def test_auth_invalid_token(async_client: AsyncClient) -> None:
    """Verify endpoints reject requests with invalid Bearer tokens."""
    headers = {"Authorization": "Bearer ak_invalid_nonexistent_token_12345"}
    response = await async_client.get("/api/v1/conversations", headers=headers)
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_auth_inactive_api_key(
    async_client: AsyncClient,
    inactive_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify endpoints reject requests from deactivated API keys with 401 UNAUTHORIZED."""
    _, _, headers = inactive_api_key
    response = await async_client.get("/api/v1/conversations", headers=headers)
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_cross_tenant_isolation(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    secondary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify strict tenant boundary isolation between distinct API keys.

    Key A must never be able to read, modify, or list Key B's conversations.
    Access attempts return 404 CONVERSATION_NOT_FOUND to prevent ID enumeration.
    """
    _, _, headers_a = primary_api_key
    _, _, headers_b = secondary_api_key

    # Tenant A creates a conversation
    res_create_a = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Tenant A Secret Thread", "system_prompt": "Secret prompt"},
        headers=headers_a,
    )
    assert res_create_a.status_code == 201
    conv_a_id = res_create_a.json()["id"]

    # Tenant B creates a conversation
    res_create_b = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Tenant B Thread"},
        headers=headers_b,
    )
    assert res_create_b.status_code == 201
    conv_b_id = res_create_b.json()["id"]

    # Tenant B attempts to read Tenant A's conversation -> 404 NOT FOUND
    res_b_reads_a = await async_client.get(
        f"/api/v1/conversations/{conv_a_id}",
        headers=headers_b,
    )
    assert res_b_reads_a.status_code == 404
    assert res_b_reads_a.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"

    # Tenant B attempts to delete Tenant A's conversation -> 404 NOT FOUND
    res_b_deletes_a = await async_client.delete(
        f"/api/v1/conversations/{conv_a_id}",
        headers=headers_b,
    )
    assert res_b_deletes_a.status_code == 404
    assert res_b_deletes_a.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"

    # Tenant B lists conversations -> only sees Tenant B's threads
    res_list_b = await async_client.get(
        "/api/v1/conversations",
        headers=headers_b,
    )
    assert res_list_b.status_code == 200
    b_items = res_list_b.json()["items"]
    b_ids = [item["id"] for item in b_items]
    assert conv_b_id in b_ids
    assert conv_a_id not in b_ids

    # Tenant A lists conversations -> only sees Tenant A's threads
    res_list_a = await async_client.get(
        "/api/v1/conversations",
        headers=headers_a,
    )
    assert res_list_a.status_code == 200
    a_items = res_list_a.json()["items"]
    a_ids = [item["id"] for item in a_items]
    assert conv_a_id in a_ids
    assert conv_b_id not in a_ids
