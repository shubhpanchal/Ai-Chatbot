"""Comprehensive security and edge-case integration tests.

Covers:
1. Authentication: invalid keys, inactive keys, malformed headers.
2. Tenant isolation: cross-tenant access to conversation CRUD, sync chat, and streaming.
3. Idempotency isolation: cross-tenant idempotency key collisions.
4. Payload validation: oversized messages, titles, system prompts, malformed JSON.
5. Path parameter validation: invalid UUIDs.
6. Pagination validation: page < 1, page_size < 1, page_size > 100.
7. Soft-delete access semantics.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_raw_api_key, hash_api_key
from app.models.api_key import APIKey


@pytest.mark.asyncio
async def test_auth_invalid_api_key(async_client: AsyncClient) -> None:
    """Verify that requests with invalid API keys return 401 UNAUTHORIZED."""
    headers = {"Authorization": "Bearer ak_invalid_nonexistent_key_99999"}
    res = await async_client.get("/api/v1/conversations", headers=headers)
    assert res.status_code == 401
    body = res.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert "Invalid or inactive API key" in body["error"]["message"]


@pytest.mark.asyncio
async def test_auth_inactive_api_key(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify that requests with inactive API keys return 401 UNAUTHORIZED."""
    raw_key = generate_raw_api_key(prefix="ak_inactive")
    key_hash = hash_api_key(raw_key, settings.api_key_secret)
    api_key = APIKey(
        id=uuid.uuid4(),
        name="Deactivated Tenant",
        key_hash=key_hash,
        is_active=False,
    )
    db_session.add(api_key)
    await db_session.commit()

    headers = {"Authorization": f"Bearer {raw_key}"}
    res = await async_client.get("/api/v1/conversations", headers=headers)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_auth_malformed_headers(async_client: AsyncClient) -> None:
    """Verify that requests with missing or malformed Authorization headers return 401."""
    # 1. Missing header
    res1 = await async_client.get("/api/v1/conversations")
    assert res1.status_code == 401
    assert res1.json()["error"]["code"] == "UNAUTHORIZED"

    # 2. Non-Bearer auth scheme
    res2 = await async_client.get(
        "/api/v1/conversations",
        headers={"Authorization": "Basic dXNlcjpwYXNzd29yZA=="},
    )
    assert res2.status_code == 401
    assert res2.json()["error"]["code"] == "UNAUTHORIZED"

    # 3. Empty Bearer token
    res3 = await async_client.get(
        "/api/v1/conversations",
        headers={"Authorization": "Bearer "},
    )
    assert res3.status_code == 401
    assert res3.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_cross_tenant_isolation_all_endpoints(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    secondary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify that Tenant B cannot access, modify, or send messages in Tenant A's conversation."""
    _, _, headers_a = primary_api_key
    _, _, headers_b = secondary_api_key

    # Tenant A creates conversation
    create_res = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Tenant A Secret Conversation"},
        headers=headers_a,
    )
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    # Tenant B attempts GET
    get_res = await async_client.get(f"/api/v1/conversations/{conv_id}", headers=headers_b)
    assert get_res.status_code == 404
    assert get_res.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"

    # Tenant B attempts DELETE
    del_res = await async_client.delete(f"/api/v1/conversations/{conv_id}", headers=headers_b)
    assert del_res.status_code == 404

    # Tenant B attempts Sync POST message
    msg_res = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Attempted cross-tenant message"},
        headers=headers_b,
    )
    assert msg_res.status_code == 404

    # Tenant B attempts Stream POST message
    stream_res = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages/stream",
        json={"content": "Attempted cross-tenant stream"},
        headers=headers_b,
    )
    assert stream_res.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_idempotency_isolation(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    secondary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify that identical idempotency keys used by different tenants do not collide or leak."""
    _, _, headers_a = primary_api_key
    _, _, headers_b = secondary_api_key

    # Tenant A creates conversation
    conv_a = (
        await async_client.post(
            "/api/v1/conversations",
            json={"title": "Tenant A Conv"},
            headers=headers_a,
        )
    ).json()["id"]

    # Tenant B creates conversation
    conv_b = (
        await async_client.post(
            "/api/v1/conversations",
            json={"title": "Tenant B Conv"},
            headers=headers_b,
        )
    ).json()["id"]

    shared_idempotency_key = "shared-uuid-idemp-12345"

    # Tenant A sends message with idempotency key
    res_a = await async_client.post(
        f"/api/v1/conversations/{conv_a}/messages",
        json={"content": "Tenant A query"},
        headers={**headers_a, "X-Idempotency-Key": shared_idempotency_key},
    )
    assert res_a.status_code == 200
    msg_id_a = res_a.json()["id"]

    # Tenant B sends message with same idempotency key
    res_b = await async_client.post(
        f"/api/v1/conversations/{conv_b}/messages",
        json={"content": "Tenant B query"},
        headers={**headers_b, "X-Idempotency-Key": shared_idempotency_key},
    )
    assert res_b.status_code == 200
    msg_id_b = res_b.json()["id"]

    # IDs must be different because idempotency is tenant-scoped
    assert msg_id_a != msg_id_b


@pytest.mark.asyncio
async def test_payload_validation_oversized_limits(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify that oversized inputs exceed max_length and return 422 VALIDATION_ERROR."""
    _, _, headers = primary_api_key

    # 1. Oversized Conversation Title (>255 chars)
    res1 = await async_client.post(
        "/api/v1/conversations",
        json={"title": "X" * 256},
        headers=headers,
    )
    assert res1.status_code == 422
    assert res1.json()["error"]["code"] == "VALIDATION_ERROR"

    # 2. Oversized System Prompt (>10,000 chars)
    res2 = await async_client.post(
        "/api/v1/conversations",
        json={"title": "Valid Title", "system_prompt": "S" * 10001},
        headers=headers,
    )
    assert res2.status_code == 422

    # 3. Create valid conversation for message test
    conv_id = (
        await async_client.post(
            "/api/v1/conversations",
            json={"title": "Message Limit Test"},
            headers=headers,
        )
    ).json()["id"]

    # 4. Oversized Message Content (>100,000 chars)
    res3 = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "M" * 100001},
        headers=headers,
    )
    assert res3.status_code == 422
    assert res3.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_malformed_json_and_invalid_types(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify that malformed JSON payloads return 422 VALIDATION_ERROR."""
    _, _, headers = primary_api_key

    raw_headers = {**headers, "Content-Type": "application/json"}
    res = await async_client.post(
        "/api/v1/conversations",
        content=b"{invalid_json: true,}",
        headers=raw_headers,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_invalid_uuid_path_parameters(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify that non-UUID path parameters return 422 VALIDATION_ERROR."""
    _, _, headers = primary_api_key

    res1 = await async_client.get("/api/v1/conversations/not-a-valid-uuid", headers=headers)
    assert res1.status_code == 422
    assert res1.json()["error"]["code"] == "VALIDATION_ERROR"

    res2 = await async_client.delete("/api/v1/conversations/12345", headers=headers)
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_pagination_boundary_validation(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify pagination validation on boundary conditions."""
    _, _, headers = primary_api_key

    # page < 1
    res1 = await async_client.get("/api/v1/conversations?page=0", headers=headers)
    assert res1.status_code == 422

    # page_size < 1
    res2 = await async_client.get("/api/v1/conversations?page_size=0", headers=headers)
    assert res2.status_code == 422

    # page_size > 100
    res3 = await async_client.get("/api/v1/conversations?page_size=101", headers=headers)
    assert res3.status_code == 422


@pytest.mark.asyncio
async def test_soft_delete_lifecycle_and_access(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
) -> None:
    """Verify soft-deleted conversations cannot be accessed or listed."""
    _, _, headers = primary_api_key

    # Create conversation
    conv_id = (
        await async_client.post(
            "/api/v1/conversations",
            json={"title": "To Be Deleted"},
            headers=headers,
        )
    ).json()["id"]

    # Delete conversation
    del_res = await async_client.delete(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert del_res.status_code == 204

    # Subsequent GET returns 404
    get_res = await async_client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert get_res.status_code == 404

    # Subsequent POST message returns 404
    msg_res = await async_client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Hello in deleted conversation"},
        headers=headers,
    )
    assert msg_res.status_code == 404

    # List conversations excludes deleted conversation
    list_res = await async_client.get("/api/v1/conversations", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert all(item["id"] != conv_id for item in items)
