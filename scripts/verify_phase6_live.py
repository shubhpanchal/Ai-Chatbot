"""Live end-to-end verification script for Phase 6 SSE Streaming & Cancellation."""

import asyncio
import json
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import generate_raw_api_key, hash_api_key
from app.models.api_key import APIKey
from app.models.llm_request import LLMRequest
from app.models.message import Message


def parse_sse_events(raw_body: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse raw SSE text stream into list of (event_type, json_data) tuples."""
    events: list[tuple[str, dict[str, Any]]] = []
    blocks = raw_body.strip().split("\n\n")
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().split("\n")
        event_type = "message"
        data_str = ""
        for line in lines:
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_str = line.split(":", 1)[1].strip()
        if data_str:
            events.append((event_type, json.loads(data_str)))
    return events


async def main() -> None:
    print("=== Phase 6 Live SSE Streaming Verification Starting ===")
    base_url = "http://localhost:8001"

    # 1. Health check
    async with httpx.AsyncClient(base_url=base_url) as client:
        res = await client.get("/health")
        assert res.status_code == 200
        print(f"1. Health Check: {res.status_code} -> {res.json()}")

    # 2. Setup test keys
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    raw_key_a = generate_raw_api_key(prefix="ak_live_stream_a")
    key_hash_a = hash_api_key(raw_key_a, settings.api_key_secret)

    raw_key_b = generate_raw_api_key(prefix="ak_live_stream_b")
    key_hash_b = hash_api_key(raw_key_b, settings.api_key_secret)

    async with session_factory() as session:
        key_a = APIKey(
            id=uuid.uuid4(),
            name="Live Stream Tenant A",
            key_hash=key_hash_a,
            is_active=True,
        )
        key_b = APIKey(
            id=uuid.uuid4(),
            name="Live Stream Tenant B",
            key_hash=key_hash_b,
            is_active=True,
        )
        session.add_all([key_a, key_b])
        await session.commit()
        print(f"2. Created test API keys for Tenant A ({key_a.id}) and Tenant B ({key_b.id})")

    headers_a = {"Authorization": f"Bearer {raw_key_a}"}
    headers_b = {"Authorization": f"Bearer {raw_key_b}"}

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # 3. Create conversation
        conv_res = await client.post(
            "/api/v1/conversations",
            json={
                "title": "Live SSE Streaming Thread",
                "system_prompt": "You are a streaming test bot.",
            },
            headers=headers_a,
        )
        assert conv_res.status_code == 201
        conv_id = conv_res.json()["id"]
        print(f"3. Tenant A created conversation {conv_id}")

        # 4. Stream message with Idempotency-Key
        idem_key = f"live-stream-idem-{uuid.uuid4()}"
        msg_payload = {"content": "Describe how token streaming works in distributed systems."}
        msg_headers = {**headers_a, "Idempotency-Key": idem_key}

        stream_res = await client.post(
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json=msg_payload,
            headers=msg_headers,
        )
        assert stream_res.status_code == 200
        assert "text/event-stream" in stream_res.headers.get("content-type", "")

        events = parse_sse_events(stream_res.text)
        token_events = [d for t, d in events if t == "token"]
        done_events = [d for t, d in events if t == "done"]

        print("4. SSE Stream received successfully:")
        print(f"   - Total token chunks received: {len(token_events)}")
        print(f"   - Done event: {done_events[0]}")
        streamed_text = "".join(str(tok["token"]) for tok in token_events)
        print(f"   - Reconstructed text: {streamed_text[:60]}...")

        # 5. Idempotency replay with same Idempotency-Key
        replay_res = await client.post(
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json=msg_payload,
            headers=msg_headers,
        )
        assert replay_res.status_code == 200
        events_replay = parse_sse_events(replay_res.text)
        done_replay = [d for t, d in events_replay if t == "done"]
        assert done_events[0]["message_id"] == done_replay[0]["message_id"]
        print("5. Idempotency Replay verified on streaming endpoint (same message_id returned).")

        # 6. Cross-tenant isolation on streaming endpoint
        cross_res = await client.post(
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"content": "Malicious stream attempt"},
            headers=headers_b,
        )
        assert cross_res.status_code == 404
        print("6. Cross-tenant streaming rejected with HTTP 404 Not Found.")

    # 7. Verify Database Records
    async with session_factory() as session:
        # Check messages
        msg_stmt = (
            select(Message)
            .where(Message.conversation_id == uuid.UUID(conv_id))
            .order_by(Message.created_at.asc())
        )
        messages = (await session.execute(msg_stmt)).scalars().all()
        print("7. Database verification:")
        print(f"   - Total persisted messages: {len(messages)}")
        for m in messages:
            print(f"     * [{m.role}] {m.content[:45]}...")
        assert len(messages) == 2  # 1 user + 1 assistant

        # Check llm_requests
        llm_stmt = (
            select(LLMRequest)
            .where(LLMRequest.conversation_id == uuid.UUID(conv_id))
            .order_by(LLMRequest.created_at.asc())
        )
        llm_requests = (await session.execute(llm_stmt)).scalars().all()
        print(f"   - Total persisted llm_requests: {len(llm_requests)}")
        for req in llm_requests:
            print(
                f"     * Model={req.model}, Status={req.status}, PromptToks={req.prompt_tokens}, "
                f"CompToks={req.completion_tokens}, Latency={req.latency_ms}ms, Cost=${req.estimated_cost}"
            )
        assert len(llm_requests) == 1

    await engine.dispose()
    print("=== ALL LIVE PHASE 6 STREAMING VERIFICATION CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
