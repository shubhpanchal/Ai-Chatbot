"""Pytest test suite executing all cases from the deterministic evaluation dataset."""

from __future__ import annotations

import json
import os
from typing import Any

import pytest
from httpx import AsyncClient

from app.models.api_key import APIKey

DATASET_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "evaluation", "dataset.json")
)


def load_eval_cases() -> list[dict[str, Any]]:
    with open(DATASET_PATH, encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)
        return data


@pytest.mark.asyncio
@pytest.mark.parametrize("case", load_eval_cases(), ids=lambda c: c["id"])
async def test_eval_case(
    async_client: AsyncClient,
    primary_api_key: tuple[APIKey, str, dict[str, str]],
    case: dict[str, Any],
) -> None:
    """Execute evaluation case and verify contract and behavioral compliance."""
    _, _, headers = primary_api_key

    # 1. Create conversation
    conv_payload: dict[str, Any] = {"title": f"Test {case['id']}: {case['title']}"}
    if case.get("system_prompt"):
        conv_payload["system_prompt"] = case["system_prompt"]

    conv_res = await async_client.post("/api/v1/conversations", json=conv_payload, headers=headers)
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    expected = case["expected_behavior"]

    # 2. Execute turns
    for msg in case["messages"]:
        msg_res = await async_client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": msg["content"]},
            headers=headers,
        )

        if expected.get("status_code") != 200:
            assert msg_res.status_code == expected["status_code"]
            if "error_code" in expected:
                assert msg_res.json()["error"]["code"] == expected["error_code"]
            return

        assert msg_res.status_code == 200
        data = msg_res.json()
        assert data["role"] == "assistant"
        assert len(data["content"]) > 0
        if "min_tokens" in expected and data.get("usage"):
            assert data["usage"]["total_tokens"] >= expected["min_tokens"]

    # 3. Verify history
    if "history_length" in expected:
        detail_res = await async_client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
        assert detail_res.status_code == 200
        assert len(detail_res.json()["messages"]) == expected["history_length"]
