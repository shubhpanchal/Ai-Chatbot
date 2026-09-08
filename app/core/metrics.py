"""Thread-safe, asynchronous in-memory metrics collector with bounded dimensions."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any


class MetricsRegistry:
    """In-memory metrics registry for HTTP, LLM, infrastructure, and application events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        """Reset all metrics to initial states (useful for tests)."""
        with self._lock:
            # 1. HTTP Metrics
            self.http_requests_total: dict[tuple[str, str, int], int] = defaultdict(int)
            self.http_durations: dict[tuple[str, str], list[float]] = defaultdict(list)

            # 2. LLM Metrics
            self.llm_requests_total: dict[tuple[str, str, str], int] = defaultdict(int)
            self.llm_durations: dict[tuple[str, str], list[float]] = defaultdict(list)
            self.llm_stream_ttft_ms: dict[tuple[str, str], list[float]] = defaultdict(list)
            self.llm_tokens_total: dict[tuple[str, str, str], int] = defaultdict(int)
            self.llm_estimated_cost_usd: dict[tuple[str, str], float] = defaultdict(float)
            self.llm_retries_total: dict[tuple[str, str], int] = defaultdict(int)

            # 3. Infrastructure Metrics
            self.db_operations_total: dict[tuple[str, str], int] = defaultdict(int)
            self.redis_operations_total: dict[tuple[str, str], int] = defaultdict(int)
            self.rate_limit_rejections_total: int = 0

            # 4. Application Metrics
            self.idempotency_hits_total: int = 0
            self.idempotency_conflicts_total: int = 0
            self.conversation_operations_total: dict[str, int] = defaultdict(int)
            self.streaming_cancellations_total: int = 0

    # --- HTTP Recording ---
    def record_http_request(
        self, method: str, route: str, status_code: int, duration_ms: float
    ) -> None:
        """Record HTTP request count and latency."""
        with self._lock:
            self.http_requests_total[(method.upper(), route, status_code)] += 1
            # Keep bounded window of recent durations for stats
            durations = self.http_durations[(method.upper(), route)]
            if len(durations) >= 1000:
                durations.pop(0)
            durations.append(duration_ms)

    # --- LLM Recording ---
    def record_llm_request(
        self, provider: str, model: str, status: str, duration_ms: float
    ) -> None:
        """Record LLM call completion by provider, model, and status (success/error/cancelled)."""
        with self._lock:
            self.llm_requests_total[(provider, model, status)] += 1
            durations = self.llm_durations[(provider, model)]
            if len(durations) >= 1000:
                durations.pop(0)
            durations.append(duration_ms)

    def record_tokens(
        self, provider: str, model: str, prompt_tokens: int, completion_tokens: int
    ) -> None:
        """Record token consumption counts."""
        with self._lock:
            self.llm_tokens_total[(provider, model, "prompt")] += prompt_tokens
            self.llm_tokens_total[(provider, model, "completion")] += completion_tokens
            self.llm_tokens_total[(provider, model, "total")] += prompt_tokens + completion_tokens

    def record_cost(self, provider: str, model: str, cost_usd: float) -> None:
        """Record estimated financial cost in USD."""
        with self._lock:
            self.llm_estimated_cost_usd[(provider, model)] += cost_usd

    def record_stream_ttft(self, provider: str, model: str, ttft_ms: float) -> None:
        """Record Time To First Token for streaming requests."""
        with self._lock:
            ttfts = self.llm_stream_ttft_ms[(provider, model)]
            if len(ttfts) >= 1000:
                ttfts.pop(0)
            ttfts.append(ttft_ms)

    def record_llm_retry(self, provider: str, model: str) -> None:
        """Record an LLM retry attempt."""
        with self._lock:
            self.llm_retries_total[(provider, model)] += 1

    # --- Infrastructure Recording ---
    def record_db_op(self, operation: str, status: str = "success") -> None:
        """Record database operation (read/write/error)."""
        with self._lock:
            self.db_operations_total[(operation, status)] += 1

    def record_redis_op(self, operation: str, status: str = "success") -> None:
        """Record Redis operation (get/set/eval/error)."""
        with self._lock:
            self.redis_operations_total[(operation, status)] += 1

    def record_rate_limit_rejection(self) -> None:
        """Record rate limit 429 rejection."""
        with self._lock:
            self.rate_limit_rejections_total += 1

    # --- Application Recording ---
    def record_idempotency_hit(self) -> None:
        """Record cached idempotency response replay."""
        with self._lock:
            self.idempotency_hits_total += 1

    def record_idempotency_conflict(self) -> None:
        """Record concurrent in-flight idempotency conflict."""
        with self._lock:
            self.idempotency_conflicts_total += 1

    def record_conversation_op(self, operation: str) -> None:
        """Record conversation lifecycle operation (create/list/get/delete)."""
        with self._lock:
            self.conversation_operations_total[operation] += 1

    def record_streaming_cancellation(self) -> None:
        """Record client disconnect stream cancellation."""
        with self._lock:
            self.streaming_cancellations_total += 1

    # --- Snapshot Export ---
    def get_snapshot(self) -> dict[str, Any]:
        """Return a structured dictionary snapshot of current metrics."""
        with self._lock:
            http_reqs = [
                {"method": m, "route": r, "status_code": s, "count": count}
                for (m, r, s), count in self.http_requests_total.items()
            ]

            llm_reqs = [
                {"provider": p, "model": m, "status": s, "count": count}
                for (p, m, s), count in self.llm_requests_total.items()
            ]

            llm_tokens = [
                {"provider": p, "model": m, "type": t, "count": count}
                for (p, m, t), count in self.llm_tokens_total.items()
            ]

            llm_costs = [
                {"provider": p, "model": m, "estimated_cost_usd": round(cost, 6)}
                for (p, m), cost in self.llm_estimated_cost_usd.items()
            ]

            llm_retries = [
                {"provider": p, "model": m, "retries": count}
                for (p, m), count in self.llm_retries_total.items()
            ]

            ttft_summary = {}
            for (p, m), ttft_list in self.llm_stream_ttft_ms.items():
                if ttft_list:
                    ttft_summary[f"{p}:{m}"] = {
                        "count": len(ttft_list),
                        "avg_ms": round(sum(ttft_list) / len(ttft_list), 2),
                        "min_ms": round(min(ttft_list), 2),
                        "max_ms": round(max(ttft_list), 2),
                    }

            return {
                "http": {
                    "requests": http_reqs,
                },
                "llm": {
                    "requests": llm_reqs,
                    "tokens": llm_tokens,
                    "costs": llm_costs,
                    "retries": llm_retries,
                    "ttft": ttft_summary,
                },
                "infrastructure": {
                    "rate_limit_rejections": self.rate_limit_rejections_total,
                    "db_operations": [
                        {"operation": op, "status": st, "count": count}
                        for (op, st), count in self.db_operations_total.items()
                    ],
                    "redis_operations": [
                        {"operation": op, "status": st, "count": count}
                        for (op, st), count in self.redis_operations_total.items()
                    ],
                },
                "application": {
                    "idempotency_hits": self.idempotency_hits_total,
                    "idempotency_conflicts": self.idempotency_conflicts_total,
                    "conversation_operations": dict(self.conversation_operations_total),
                    "streaming_cancellations": self.streaming_cancellations_total,
                },
            }


# Global metrics registry singleton
metrics = MetricsRegistry()
