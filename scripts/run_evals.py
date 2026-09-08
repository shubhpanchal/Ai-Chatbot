"""Deterministic Evaluation Suite Runner for Phase 9.

Executes all test cases from evaluation/dataset.json against the API,
records per-case metrics (status, tokens, cost, latency, pass/fail),
and writes a machine-readable summary to evaluation/eval_results.json.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.security import generate_raw_api_key, hash_api_key
from app.models.api_key import APIKey

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5434/ai_chat_db",
)
DATASET_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "evaluation", "dataset.json")
)
RESULTS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "evaluation", "eval_results.json")
)


async def setup_eval_tenant(session: AsyncSession) -> tuple[APIKey, str, dict[str, str]]:
    """Create a dedicated tenant API key for the evaluation run."""
    raw_key = generate_raw_api_key(prefix="ak_eval")
    key_hash = hash_api_key(raw_key, settings.api_key_secret)
    api_key = APIKey(
        id=uuid.uuid4(),
        name="Evaluation Runner Tenant",
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


async def run_single_eval_case(
    client: httpx.AsyncClient,
    case: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    """Execute a single multi-turn evaluation case and assess behavior against expectations."""
    case_id = case["id"]
    category = case["category"]
    title = case["title"]
    system_prompt = case.get("system_prompt")
    messages = case["messages"]
    expected = case["expected_behavior"]

    start_case_time = time.perf_counter()
    total_tokens = 0
    total_cost_usd = 0.0
    turn_latencies_ms: list[float] = []
    responses: list[dict[str, Any]] = []

    # 1. Create conversation thread
    conv_payload: dict[str, Any] = {"title": f"Eval Case {case_id}: {title}"}
    if system_prompt:
        conv_payload["system_prompt"] = system_prompt

    conv_res = await client.post("/api/v1/conversations", json=conv_payload, headers=headers)
    if conv_res.status_code != 201:
        return {
            "id": case_id,
            "category": category,
            "title": title,
            "status": "FAILED",
            "reason": f"Failed to create conversation: {conv_res.status_code} {conv_res.text}",
            "latency_ms": round((time.perf_counter() - start_case_time) * 1000, 2),
        }

    conv_id = conv_res.json()["id"]

    # 2. Execute turns sequentially
    for msg in messages:
        user_content = msg["content"]
        turn_start = time.perf_counter()

        msg_res = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": user_content},
            headers=headers,
        )
        turn_latency = (time.perf_counter() - turn_start) * 1000
        turn_latencies_ms.append(round(turn_latency, 2))

        # Check for expected error case (e.g. empty message)
        if expected.get("status_code") != 200:
            if msg_res.status_code == expected["status_code"]:
                error_body = msg_res.json()
                if (
                    "error_code" not in expected
                    or error_body.get("error", {}).get("code") == expected["error_code"]
                ):
                    return {
                        "id": case_id,
                        "category": category,
                        "title": title,
                        "status": "PASSED",
                        "status_code": msg_res.status_code,
                        "expected_error": expected.get("error_code"),
                        "total_latency_ms": round(
                            (time.perf_counter() - start_case_time) * 1000, 2
                        ),
                    }
            return {
                "id": case_id,
                "category": category,
                "title": title,
                "status": "FAILED",
                "reason": f"Expected status {expected.get('status_code')}, got {msg_res.status_code}",
                "total_latency_ms": round((time.perf_counter() - start_case_time) * 1000, 2),
            }

        if msg_res.status_code != 200:
            return {
                "id": case_id,
                "category": category,
                "title": title,
                "status": "FAILED",
                "reason": f"Message turn failed with status {msg_res.status_code}: {msg_res.text}",
                "total_latency_ms": round((time.perf_counter() - start_case_time) * 1000, 2),
            }

        resp_data = msg_res.json()
        responses.append(resp_data)
        if resp_data.get("usage"):
            total_tokens += resp_data["usage"]["total_tokens"]
            total_cost_usd += resp_data["usage"]["estimated_cost_usd"]

    # 3. Validate conversation history state
    detail_res = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert detail_res.status_code == 200
    conv_detail = detail_res.json()

    if "history_length" in expected:
        actual_len = len(conv_detail["messages"])
        if actual_len != expected["history_length"]:
            return {
                "id": case_id,
                "category": category,
                "title": title,
                "status": "FAILED",
                "reason": f"Expected history length {expected['history_length']}, got {actual_len}",
                "total_latency_ms": round((time.perf_counter() - start_case_time) * 1000, 2),
            }

    total_latency_ms = round((time.perf_counter() - start_case_time) * 1000, 2)
    return {
        "id": case_id,
        "category": category,
        "title": title,
        "status": "PASSED",
        "turns_count": len(messages),
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost_usd, 6),
        "turn_latencies_ms": turn_latencies_ms,
        "total_latency_ms": total_latency_ms,
        "history_length": len(conv_detail["messages"]),
    }


async def main() -> None:
    print("=== Running Phase 9 Evaluation Suite ===")

    with open(DATASET_PATH, encoding="utf-8") as f:
        cases = json.load(f)

    print(f"Loaded {len(cases)} evaluation test cases from {DATASET_PATH}")

    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        tenant, _, headers = await setup_eval_tenant(session)
    print(f"Provisioned evaluation tenant: {tenant.id}")

    results: list[dict[str, Any]] = []
    passed_count = 0
    failed_count = 0

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        for case in cases:
            print(f"Running [{case['id']}] {case['title']} ({case['category']})...", end=" ")
            res = await run_single_eval_case(client, case, headers)
            results.append(res)
            if res["status"] == "PASSED":
                passed_count += 1
                print("PASSED")
            else:
                failed_count += 1
                print(f"FAILED ({res.get('reason')})")

    await engine.dispose()

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_cases": len(cases),
        "passed_cases": passed_count,
        "failed_cases": failed_count,
        "pass_rate_pct": round((passed_count / len(cases)) * 100, 2),
        "results": results,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(
        f"\nEvaluation Complete: {passed_count}/{len(cases)} Passed ({summary['pass_rate_pct']}%)"
    )
    print(f"Results written to: {RESULTS_PATH}")

    if failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
