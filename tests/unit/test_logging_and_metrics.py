"""Unit tests for structured logging redactor and metrics registry."""

from __future__ import annotations

import structlog

from app.core.logging import redact_sensitive_data
from app.core.metrics import MetricsRegistry


def test_redact_sensitive_data_keys_and_patterns() -> None:
    """Verify that sensitive keys, API keys, and Bearer tokens are redacted."""
    event_dict = {
        "event": "test_event",
        "authorization": "Bearer ak_live_12345678901234567890",
        "api_key": "ak_test_secretkey1234567890",
        "password": "supersecretpassword",
        "secret": "my-pepper-secret",
        "prompt": "Classified instructions",
        "raw_text_with_embedded_token": "Error in auth: Bearer ak_embedded_12345678901234567890 failed",
        "safe_field": "public_data",
        "status_code": 200,
    }

    redacted = redact_sensitive_data(None, "info", event_dict)

    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["secret"] == "[REDACTED]"
    assert redacted["prompt"] == "[REDACTED]"
    assert redacted["safe_field"] == "public_data"
    assert redacted["status_code"] == 200
    assert "ak_embedded" not in redacted["raw_text_with_embedded_token"]
    assert "[REDACTED]" in redacted["raw_text_with_embedded_token"]


def test_metrics_registry_recording_and_snapshot() -> None:
    """Verify MetricsRegistry accumulates counters, histograms, and generates snapshots."""
    registry = MetricsRegistry()

    # 1. HTTP recording
    registry.record_http_request("POST", "/api/v1/conversations", 201, 45.2)
    registry.record_http_request("POST", "/api/v1/conversations", 201, 55.8)
    registry.record_http_request("GET", "/api/v1/conversations", 200, 12.0)

    # 2. LLM recording
    registry.record_llm_request("openai", "gpt-4o-mini", "success", 340.5)
    registry.record_tokens("openai", "gpt-4o-mini", prompt_tokens=25, completion_tokens=50)
    registry.record_cost("openai", "gpt-4o-mini", cost_usd=0.000045)
    registry.record_stream_ttft("openai", "gpt-4o-mini", ttft_ms=120.0)
    registry.record_stream_ttft("openai", "gpt-4o-mini", ttft_ms=140.0)
    registry.record_llm_retry("openai", "gpt-4o-mini")

    # 3. Infrastructure & App recording
    registry.record_db_op("create_conversation", "success")
    registry.record_redis_op("rate_limit_eval", "success")
    registry.record_rate_limit_rejection()
    registry.record_idempotency_hit()
    registry.record_idempotency_conflict()
    registry.record_conversation_op("create")
    registry.record_streaming_cancellation()

    snapshot = registry.get_snapshot()

    # Verify HTTP snapshot
    assert len(snapshot["http"]["requests"]) == 2
    post_req = next(r for r in snapshot["http"]["requests"] if r["method"] == "POST")
    assert post_req["count"] == 2

    # Verify LLM snapshot
    assert snapshot["llm"]["requests"][0]["status"] == "success"
    assert snapshot["llm"]["requests"][0]["count"] == 1
    assert snapshot["llm"]["ttft"]["openai:gpt-4o-mini"]["count"] == 2
    assert snapshot["llm"]["ttft"]["openai:gpt-4o-mini"]["avg_ms"] == 130.0

    # Verify token & cost
    prompt_tokens_entry = next(t for t in snapshot["llm"]["tokens"] if t["type"] == "prompt")
    assert prompt_tokens_entry["count"] == 25
    assert snapshot["llm"]["costs"][0]["estimated_cost_usd"] == 0.000045
    assert snapshot["llm"]["retries"][0]["retries"] == 1

    # Verify infrastructure & app
    assert snapshot["infrastructure"]["rate_limit_rejections"] == 1
    assert snapshot["application"]["idempotency_hits"] == 1
    assert snapshot["application"]["idempotency_conflicts"] == 1
    assert snapshot["application"]["conversation_operations"]["create"] == 1
    assert snapshot["application"]["streaming_cancellations"] == 1


def test_structlog_contextvars_binding() -> None:
    """Verify structlog context variables are properly bound and cleared."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id="req-test-uuid-12345")

    context = structlog.contextvars.get_contextvars()
    assert context["request_id"] == "req-test-uuid-12345"

    structlog.contextvars.clear_contextvars()
    assert "request_id" not in structlog.contextvars.get_contextvars()
