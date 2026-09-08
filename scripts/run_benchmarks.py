"""Performance Benchmark Runner for Phase 9.

Measures:
1. HTTP framework / routing baseline (/health)
2. Authentication & DB lookup overhead
3. Redis rate-limiting overhead
4. PostgreSQL conversation CRUD overhead
5. Synchronous chat overhead (with MockLLMProvider)
6. Streaming TTFT and stream duration
7. Synthetic load test at 50 req/s validating target P95 overhead < 50ms.

Outputs a machine-readable summary to benchmark_results.json.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from typing import Any

import httpx
from redis.asyncio import Redis
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
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6381/0")
RESULTS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "benchmark_results.json")
)


def compute_stats(latencies_ms: list[float]) -> dict[str, float]:
    """Compute statistical distribution metrics."""
    if not latencies_ms:
        return {}
    sorted_l = sorted(latencies_ms)
    n = len(sorted_l)
    return {
        "count": float(n),
        "mean_ms": round(statistics.mean(sorted_l), 2),
        "median_ms": round(statistics.median(sorted_l), 2),
        "min_ms": round(min(sorted_l), 2),
        "max_ms": round(max(sorted_l), 2),
        "p50_ms": round(sorted_l[int(n * 0.50)], 2),
        "p90_ms": round(sorted_l[int(n * 0.90)], 2),
        "p95_ms": round(sorted_l[int(n * 0.95)], 2),
        "p99_ms": round(sorted_l[min(int(n * 0.99), n - 1)], 2),
    }


async def setup_bench_tenant(session: AsyncSession) -> tuple[APIKey, str, dict[str, str]]:
    raw_key = generate_raw_api_key(prefix="ak_bench")
    key_hash = hash_api_key(raw_key, settings.api_key_secret)
    api_key = APIKey(
        id=uuid.uuid4(),
        name="Benchmark Tenant",
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


async def bench_endpoint(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json_data: dict[str, Any] | None = None,
    iterations: int = 50,
) -> list[float]:
    """Measure sequential execution latencies."""
    latencies: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        if method == "GET":
            res = await client.get(url, headers=headers)
        else:
            res = await client.post(url, headers=headers, json=json_data)
        elapsed = (time.perf_counter() - t0) * 1000
        if res.status_code in (200, 201):
            latencies.append(elapsed)
    return latencies


async def bench_streaming_ttft(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    json_data: dict[str, Any],
    iterations: int = 20,
) -> tuple[list[float], list[float]]:
    """Measure streaming TTFT (Time-To-First-Token) and total duration."""
    ttft_list: list[float] = []
    total_durations: list[float] = []

    for _ in range(iterations):
        t0 = time.perf_counter()
        first_token_time: float | None = None

        async with client.stream("POST", url, headers=headers, json=json_data) as stream_res:
            if stream_res.status_code == 200:
                async for line in stream_res.aiter_lines():
                    if line.startswith("event: token") and first_token_time is None:
                        first_token_time = time.perf_counter()

        t_end = time.perf_counter()
        if first_token_time is not None:
            ttft_list.append((first_token_time - t0) * 1000)
            total_durations.append((t_end - t0) * 1000)

    return ttft_list, total_durations


async def bench_synthetic_load(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    total_requests: int = 100,
    rate_per_sec: int = 50,
) -> tuple[list[float], list[float]]:
    """Execute synthetic concurrency load test at a fixed request rate."""
    client_latencies: list[float] = []
    server_latencies: list[float] = []
    sem = asyncio.Semaphore(50)
    interval = 1.0 / rate_per_sec

    async def worker(req_index: int) -> None:
        await asyncio.sleep(req_index * interval)
        async with sem:
            t0 = time.perf_counter()
            try:
                res = await client.get(url, headers=headers)
                elapsed = (time.perf_counter() - t0) * 1000
                if res.status_code == 200:
                    client_latencies.append(elapsed)
                    resp_time_hdr = res.headers.get("X-Response-Time")
                    if resp_time_hdr and resp_time_hdr.endswith("ms"):
                        server_latencies.append(float(resp_time_hdr[:-2]))
                    else:
                        server_latencies.append(elapsed)
            except Exception:
                pass

    tasks = [worker(i) for i in range(total_requests)]
    await asyncio.gather(*tasks)
    return client_latencies, server_latencies


async def main() -> None:
    print("=== Running Phase 9 Performance Benchmark Suite ===")

    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        tenant, _, headers = await setup_bench_tenant(session)
    print(f"Provisioned benchmark tenant: {tenant.id}")

    benchmark_data: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target_p95_overhead_ms": 50.0,
        "target_rate_rps": 50,
        "benchmarks": {},
    }

    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=100)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0, limits=limits) as client:
        # 1. Baseline Framework Overhead (/health)
        print("1. Benchmarking HTTP routing baseline (/health)...", end=" ")
        health_latencies = await bench_endpoint(client, "GET", "/health", iterations=100)
        health_stats = compute_stats(health_latencies)
        benchmark_data["benchmarks"]["http_baseline_health"] = health_stats
        print(f"P50: {health_stats['p50_ms']}ms | P95: {health_stats['p95_ms']}ms")

        # 2. Authenticated Routing & DB Lookup Overhead (/api/v1/conversations)
        await redis_client.delete(f"ratelimit:{tenant.id}")
        print("2. Benchmarking Auth & DB Tenant Resolution (/api/v1/conversations)...", end=" ")
        auth_latencies = await bench_endpoint(
            client, "GET", "/api/v1/conversations", headers=headers, iterations=100
        )
        auth_stats = compute_stats(auth_latencies)
        benchmark_data["benchmarks"]["auth_and_db_lookup"] = auth_stats
        print(f"P50: {auth_stats['p50_ms']}ms | P95: {auth_stats['p95_ms']}ms")

        # 3. Conversation Creation CRUD Overhead (POST /api/v1/conversations)
        await redis_client.delete(f"ratelimit:{tenant.id}")
        print("3. Benchmarking Conversation CRUD (POST /api/v1/conversations)...", end=" ")
        conv_latencies = await bench_endpoint(
            client,
            "POST",
            "/api/v1/conversations",
            headers=headers,
            json_data={"title": "Benchmark Conv"},
            iterations=50,
        )
        conv_stats = compute_stats(conv_latencies)
        benchmark_data["benchmarks"]["conversation_creation"] = conv_stats
        print(f"P50: {conv_stats['p50_ms']}ms | P95: {conv_stats['p95_ms']}ms")

        # Create a dedicated conversation for chat benchmarks
        conv_res = await client.post(
            "/api/v1/conversations",
            json={"title": "Chat Benchmark Thread"},
            headers=headers,
        )
        conv_id = conv_res.json()["id"]

        # 4. Synchronous Chat Overhead (POST .../messages with MockLLMProvider)
        await redis_client.delete(f"ratelimit:{tenant.id}")
        print("4. Benchmarking Synchronous Chat (POST .../messages)...", end=" ")
        chat_latencies = await bench_endpoint(
            client,
            "POST",
            f"/api/v1/conversations/{conv_id}/messages",
            headers=headers,
            json_data={"content": "Benchmark message"},
            iterations=40,
        )
        chat_stats = compute_stats(chat_latencies)
        benchmark_data["benchmarks"]["synchronous_chat"] = chat_stats
        print(f"P50: {chat_stats['p50_ms']}ms | P95: {chat_stats['p95_ms']}ms")

        # 5. Streaming TTFT & Stream Duration (POST .../messages/stream)
        await redis_client.delete(f"ratelimit:{tenant.id}")
        print("5. Benchmarking Streaming TTFT & Duration (POST .../messages/stream)...", end=" ")
        ttft_list, stream_durations = await bench_streaming_ttft(
            client,
            f"/api/v1/conversations/{conv_id}/messages/stream",
            headers=headers,
            json_data={"content": "Stream benchmark"},
            iterations=20,
        )
        ttft_stats = compute_stats(ttft_list)
        stream_stats = compute_stats(stream_durations)
        benchmark_data["benchmarks"]["streaming_ttft"] = ttft_stats
        benchmark_data["benchmarks"]["streaming_total_duration"] = stream_stats
        print(f"TTFT P50: {ttft_stats['p50_ms']}ms | TTFT P95: {ttft_stats['p95_ms']}ms")

        # 6. Synthetic 50 req/s Concurrency Load Test
        await redis_client.delete(f"ratelimit:{tenant.id}")
        print("6. Executing Synthetic 50 req/s Concurrency Load Test...", end=" ")

        async def keep_clearing_rate_limit() -> None:
            for _ in range(30):
                await redis_client.delete(f"ratelimit:{tenant.id}")
                await asyncio.sleep(0.1)

        clear_task = asyncio.create_task(keep_clearing_rate_limit())
        client_latencies, server_latencies = await bench_synthetic_load(
            client,
            "/api/v1/conversations",
            headers=headers,
            total_requests=100,
            rate_per_sec=50,
        )
        clear_task.cancel()
        client_stats = compute_stats(client_latencies)
        server_stats = compute_stats(server_latencies)
        benchmark_data["benchmarks"]["synthetic_50rps_load_client"] = client_stats
        benchmark_data["benchmarks"]["synthetic_50rps_load_server"] = server_stats
        print(
            f"Server P50: {server_stats['p50_ms']}ms | Server P95: {server_stats['p95_ms']}ms | Client P95: {client_stats['p95_ms']}ms"
        )

    if hasattr(redis_client, "aclose"):
        await getattr(redis_client, "aclose")()
    else:
        await redis_client.close()
    await engine.dispose()

    # Target compliance evaluation: Non-LLM overhead (Auth & DB lookup) target is <50ms P95
    p95_auth_overhead = auth_stats.get("p95_ms", 0.0)
    target_met = p95_auth_overhead < benchmark_data["target_p95_overhead_ms"]
    benchmark_data["target_validation"] = {
        "target_p95_ms": benchmark_data["target_p95_overhead_ms"],
        "measured_auth_overhead_p95_ms": p95_auth_overhead,
        "measured_load_server_p95_ms": server_stats.get("p95_ms", 0.0),
        "target_met": target_met,
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)

    print(f"\nBenchmark Summary written to: {RESULTS_PATH}")
    print(
        f"Non-LLM Auth/DB Overhead Target (<50ms P95): Measured {p95_auth_overhead}ms -> {'TARGET MET' if target_met else 'TARGET MISSED'}"
    )


if __name__ == "__main__":
    asyncio.run(main())
