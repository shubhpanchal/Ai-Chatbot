"""Live end-to-end verification script for Phase 5 against running Docker containers."""

import asyncio
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import generate_raw_api_key, hash_api_key
from app.models.api_key import APIKey
from app.models.llm_request import LLMRequest
from app.models.message import Message


async def main() -> None:
    print("=== Phase 5 Live Verification Starting ===")
    base_url = "http://localhost:8001"

    # 1. Check container health
    async with httpx.AsyncClient(base_url=base_url) as client:
        res = await client.get("/health")
        print(f"1. Health Check: {res.status_code} -> {res.json()}")
        assert res.status_code == 200

    # 2. Setup test API keys in PostgreSQL
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    raw_key_tenant_a = generate_raw_api_key(prefix="ak_live_a")
    key_hash_a = hash_api_key(raw_key_tenant_a, settings.api_key_secret)

    raw_key_tenant_b = generate_raw_api_key(prefix="ak_live_b")
    key_hash_b = hash_api_key(raw_key_tenant_b, settings.api_key_secret)

    async with session_factory() as session:
        key_a = APIKey(
            id=uuid.uuid4(),
            name="Live Tenant A",
            key_hash=key_hash_a,
            is_active=True,
        )
        key_b = APIKey(
            id=uuid.uuid4(),
            name="Live Tenant B",
            key_hash=key_hash_b,
            is_active=True,
        )
        session.add_all([key_a, key_b])
        await session.commit()
        print(f"2. Created test API keys for Tenant A ({key_a.id}) and Tenant B ({key_b.id})")

    headers_a = {"Authorization": f"Bearer {raw_key_tenant_a}"}
    headers_b = {"Authorization": f"Bearer {raw_key_tenant_b}"}

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # 3. Tenant A creates conversation
        conv_res = await client.post(
            "/api/v1/conversations",
            json={
                "title": "Live Phase 5 Synchronous Chat",
                "system_prompt": "You are a live verification bot.",
            },
            headers=headers_a,
        )
        assert conv_res.status_code == 201, f"Failed: {conv_res.text}"
        conv_data = conv_res.json()
        conv_id = conv_data["id"]
        print(f"3. Tenant A created conversation {conv_id} with custom system prompt")

        # 4. Synchronous chat message with Idempotency-Key
        idem_key = f"live-idem-{uuid.uuid4()}"
        msg_payload = {"content": "Hello! Explain quantum superposition in 2 sentences."}
        msg_headers = {**headers_a, "Idempotency-Key": idem_key}

        msg_res1 = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json=msg_payload,
            headers=msg_headers,
        )
        assert msg_res1.status_code == 200, f"Failed: {msg_res1.text}"
        msg_data1 = msg_res1.json()
        print("4. First synchronous chat response received:")
        print(f"   - Assistant Message ID: {msg_data1['id']}")
        print(f"   - Role: {msg_data1['role']}")
        print(f"   - Content snippet: {msg_data1['content'][:60]}...")
        print(f"   - Usage: {msg_data1['usage']}")

        # 5. Idempotency replay with same Idempotency-Key
        msg_res2 = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json=msg_payload,
            headers=msg_headers,
        )
        assert msg_res2.status_code == 200, f"Failed: {msg_res2.text}"
        msg_data2 = msg_res2.json()
        assert msg_data1["id"] == msg_data2["id"]
        assert msg_data1["created_at"] == msg_data2["created_at"]
        print(
            "5. Idempotency Replay verified! Identical response returned without duplicate execution."
        )

        # 6. Tenant B attempts to access Tenant A conversation -> 404 Forbidden/Not Found
        cross_res = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Malicious cross-tenant attempt"},
            headers=headers_b,
        )
        assert cross_res.status_code == 404
        print(
            "6. Cross-tenant isolation verified: Tenant B cannot access Tenant A conversation (HTTP 404)."
        )

        # 7. Follow-up multi-turn message from Tenant A
        msg_res3 = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Can you summarize that even further?"},
            headers=headers_a,
        )
        assert msg_res3.status_code == 200
        msg_data3 = msg_res3.json()
        print(
            f"7. Multi-turn conversation message sent and responded to successfully (ID: {msg_data3['id']})."
        )

    # 8. Verify database records
    async with session_factory() as session:
        # Check messages
        msg_stmt = (
            select(Message)
            .where(Message.conversation_id == uuid.UUID(conv_id))
            .order_by(Message.created_at.asc())
        )
        messages = (await session.execute(msg_stmt)).scalars().all()
        print("8. Database verification:")
        print(f"   - Total persisted messages in conversation: {len(messages)}")
        for m in messages:
            print(f"     * [{m.role}] {m.content[:40]}...")
        assert len(messages) == 4  # 2 user messages + 2 assistant messages

        # Check llm_requests
        llm_stmt = (
            select(LLMRequest)
            .where(LLMRequest.conversation_id == uuid.UUID(conv_id))
            .order_by(LLMRequest.created_at.asc())
        )
        llm_requests = (await session.execute(llm_stmt)).scalars().all()
        print(f"   - Total persisted llm_requests audit logs: {len(llm_requests)}")
        for req in llm_requests:
            print(
                f"     * Model={req.model}, Status={req.status}, PromptToks={req.prompt_tokens}, "
                f"CompToks={req.completion_tokens}, Latency={req.latency_ms}ms, Cost=${req.estimated_cost}"
            )
        assert (
            len(llm_requests) == 2
        )  # Exactly 2 LLM requests logged (idempotent replay did not create a 3rd)

    await engine.dispose()
    print("=== ALL LIVE PHASE 5 VERIFICATION CHECKS PASSED SUCCESSFULLY ===")


if __name__ == "__main__":
    asyncio.run(main())
