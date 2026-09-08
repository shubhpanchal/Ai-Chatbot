# Architecture Decision Records (ADRs)

This document records the foundational architectural decisions made for the **AI Chat API**, detailing the context, decision, alternatives considered, reasoning, and consequences for each.

---

## ADR-001: Adoption of FastAPI as the Core API Framework

* **Status**: Accepted
* **Context**: The application requires high concurrency for handling slow, I/O-bound LLM streaming connections, native async support, and automated OpenAPI documentation.
* **Decision**: Use **FastAPI** with Python 3.12+.
* **Alternatives Considered**:
  * *Flask*: Synchronous by default, requires third-party plugins for async, OpenAPI, and schema validation.
  * *Django/DRF*: Heavyweight, introduces complex ORM overhead, less ergonomic for lightweight async token streaming.
  * *Tornado / Sanic*: Async-native, but lacks the rich ecosystem, Pydantic v2 deep integration, and automatic documentation of FastAPI.
* **Reasoning**: FastAPI provides first-class async/await support on top of Starlette and AnyIO, seamless data validation via Pydantic v2, dependency injection, and automatic OpenAPI schema generation.
* **Consequences**: Fast development velocity, strict type safety, and native compatibility with Server-Sent Events.

---

## ADR-002: PostgreSQL as the Primary Relational Store

* **Status**: Accepted
* **Context**: Need durable persistence for multi-turn conversations, messages, audit logs, and API keys with relational integrity, transactions, and indexing capabilities.
* **Decision**: Use **PostgreSQL 16+**.
* **Alternatives Considered**:
  * *MongoDB / Document DB*: Flexible for nested messages, but lacks robust relational constraints, foreign keys for multi-tenancy, and ACID guarantees for financial/token auditing.
  * *SQLite*: Great for local dev, but unsuitable for production concurrency, connection pooling, and multi-container Docker deployments.
* **Reasoning**: Relational structure cleanly models conversations $\to$ messages $\to$ audit logs with foreign key constraints, composite indexing for sub-millisecond history retrieval, and robust ACID transactions.
* **Consequences**: Requires schema migrations via Alembic and async connection pool management via `asyncpg`.

---

## ADR-003: Redis for Rate Limiting & Distributed Idempotency

* **Status**: Accepted
* **Context**: The API must enforce rate limits across distributed workers and guarantee idempotency on retry requests without overloading PostgreSQL.
* **Decision**: Use **Redis 7+** as an in-memory data store for sliding-window rate limiting and idempotency caching.
* **Alternatives Considered**:
  * *In-Memory Python Dictionaries*: Fails across multi-worker Uvicorn processes or container replicas.
  * *PostgreSQL Tables*: High write contention and connection pool exhaustion when recording per-request rate limit timestamps.
* **Reasoning**: Redis sorted sets (`ZSET`) provide $O(\log N + M)$ sliding-window rate limiting with atomic updates and automatic TTL expiration for idempotency locks and responses.
* **Consequences**: Adds an infrastructure dependency that requires health checks and fallback/fail-open resilience.

---

## ADR-004: SQLAlchemy 2.0 (Async) and Alembic for Database Access

* **Status**: Accepted
* **Context**: Need a type-safe, async-native ORM and schema migration tool to manage PostgreSQL tables.
* **Decision**: Use **SQLAlchemy 2.x** with `asyncpg` and **Alembic** for schema migrations.
* **Alternatives Considered**:
  * *Tortoise ORM / Peewee*: Less mature migration ecosystems, smaller community support.
  * *Raw SQL with asyncpg*: Fast, but lacks type safety, model validation, relationship management, and structured schema evolution.
* **Reasoning**: SQLAlchemy 2.0 provides explicit 2.0-style queries (`select()`), first-class async engine support, declarative base models, and industry-standard migrations with Alembic.
* **Consequences**: Requires careful handling of async session lifecycles via dependency injection.

---

## ADR-005: HMAC-SHA-256 Authentication with Server-Side Secret

* **Status**: Accepted
* **Context**: Clients authenticate using API keys. Storing plaintext keys is insecure; storing plain SHA-256 hashes is vulnerable to rainbow table attacks if database snapshots leak.
* **Decision**: Store API keys as **HMAC-SHA-256** digests using a server-side pepper secret (`API_KEY_SECRET`).
* **Alternatives Considered**:
  * *Plaintext Storage*: Unacceptable security risk.
  * *Plain SHA-256*: Vulnerable to dictionary attacks on short or common keys.
  * *Bcrypt / Argon2*: High CPU overhead on every authenticated request, which conflicts with $<50\text{ ms}$ P95 API overhead targets.
* **Reasoning**: HMAC-SHA-256 provides constant-time computation, high throughput, and cryptographic resistance against precomputed rainbow table attacks via the server-side secret.
* **Consequences**: If the `API_KEY_SECRET` changes, existing keys cannot be verified. Secret must be securely injected via environment variables.

---

## ADR-006: LLM Provider Abstraction Layer

* **Status**: Accepted
* **Context**: The system uses OpenAI initially, but future extensions will require multi-provider routing (Anthropic, Gemini, local models) and zero-cost mock testing.
* **Decision**: Isolate LLM interactions behind an abstract base class (`LLMProvider`).
* **Alternatives Considered**:
  * *Direct OpenAI SDK Calls in Services*: Couples the entire application to OpenAI's SDK interface and makes unit/integration testing expensive or slow.
  * *Heavyweight Frameworks (LangChain / LlamaIndex)*: Introduces excessive layers of abstraction, unwanted dependencies, and opacity for a foundational backend project.
* **Reasoning**: A clean, minimal `LLMProvider` interface (`generate()`, `stream()`, `count_tokens()`) decouples business logic from SDK specifics and enables deterministic `MockLLMProvider` testing.
* **Consequences**: Requires manual implementation of provider adapters, but maintains clean architectural control.

---

## ADR-007: Server-Sent Events (SSE) for Response Streaming

* **Status**: Accepted
* **Context**: Users expect real-time token delivery to reduce perceived latency. Need an HTTP-compliant streaming transport.
* **Decision**: Use **Server-Sent Events (SSE)** via HTTP `text/event-stream`.
* **Alternatives Considered**:
  * *WebSockets*: Full-duplex, but requires connection upgrades, complex state management, custom heartbeat/reconnection logic, and breaks standard REST semantics.
  * *Raw Chunked Transfer*: Works, but lacks standard event framing (`event: token`, `data: ...`).
* **Reasoning**: SSE runs over standard HTTP/1.1 and HTTP/2, works natively with standard API gateways, supports client reconnection, and naturally models unidirectional LLM token streaming.
* **Consequences**: Requires client-side EventSource/fetch streaming handlers and server-side disconnect detection.

---

## ADR-008: Soft Deletion for Conversations

* **Status**: Accepted
* **Context**: When a user deletes a conversation, we must balance user privacy/UI cleanup with financial, audit, and token accounting integrity.
* **Decision**: Implement **Soft Deletion** via `deleted_at TIMESTAMPTZ NULL` on the `conversations` table.
* **Alternatives Considered**:
  * *Hard Deletion (CASCADE)*: Destroys historical `llm_requests` records, corrupting financial reports and token analytics.
  * *Hard Deletion with NULL Foreign Keys*: Leaves orphaned `llm_requests` rows with broken relational provenance.
* **Reasoning**: Setting `deleted_at = NOW()` immediately excludes the conversation from user listings while preserving historical token usage and cost records in `llm_requests`.
* **Consequences**: All read queries must include `WHERE deleted_at IS NULL`, supported by composite indexes.

---

## ADR-009: Dedicated Audit & Usage Accounting Table (`llm_requests`)

* **Status**: Accepted
* **Context**: Tracking prompt tokens, completion tokens, latency, status, and USD cost is mandatory for financial control and debugging.
* **Decision**: Create an independent `llm_requests` table linked to `conversations` and `messages`.
* **Alternatives Considered**:
  * *Denormalizing Usage onto `messages`*: Fails to capture failed LLM calls, retries, cancelled streams, or standalone evaluation queries that do not result in a persisted message.
* **Reasoning**: Isolating LLM requests provides an immutable audit log of every LLM interaction, capturing duration, model name, token counts, status (`success`, `error`, `cancelled`), and USD cost.
* **Consequences**: Requires a lightweight insert after each LLM call.

---

## ADR-010: Distributed Idempotency via `Idempotency-Key`

* **Status**: Accepted
* **Context**: Network timeouts often cause client retries. Retrying a message generation endpoint could trigger duplicate LLM calls and duplicate billing.
* **Decision**: Support the `Idempotency-Key` header, managed via Redis with lock-and-cache semantics.
* **Alternatives Considered**:
  * *No Idempotency*: Direct risk of double-billing and conversational history corruption on retries.
  * *Database-backed Unique Constraints*: Inefficient for managing transient in-progress request locks and expiration TTLs.
* **Reasoning**: Redis provides sub-millisecond atomic key locking (`SET key value NX EX 60`) and response caching (24-hour TTL), preventing concurrent duplicate processing.
* **Consequences**: Clients should supply unique UUIDs in `Idempotency-Key` headers for safe retries.

---

## ADR-011: Selective Retries with Exponential Backoff & Jitter

* **Status**: Accepted
* **Context**: External LLM APIs occasionally return transient 429 (rate limits) or 503 (temporary unavailability) errors.
* **Decision**: Implement limited retries (max 3 attempts) with exponential backoff and full jitter **only for non-streaming requests**. Do not retry streaming requests after initial token flush.
* **Alternatives Considered**:
  * *Blind Retries on All Requests*: Streaming requests that fail midway would re-stream duplicated content to the client.
  * *No Retries*: Transient network blips directly degrade user experience.
* **Reasoning**: Retrying non-streaming calls shields users from transient upstream spikes. For streaming calls, retrying after bytes have been written corrupts the SSE stream.
* **Consequences**: Streaming failures must abort cleanly and notify the client via SSE error framing.

---

## ADR-012: 5-Pillar Observability Model

* **Status**: Accepted
* **Context**: Production GenAI systems require visibility across HTTP performance, LLM generation dynamics, infrastructure health, application logs, and financial spend.
* **Decision**: Divide telemetry into 5 discrete pillars: HTTP Metrics, LLM Metrics (including TTFT), Infrastructure Metrics, Structured JSON Logs, and Cost Accounting.
* **Alternatives Considered**:
  * *Unstructured Text Logs*: Difficult to query, parse, and aggregate across distributed environments.
  * *Single-Metric Blended Dashboards*: Obscures whether latency originates from application code, database locks, or external LLM generation.
* **Reasoning**: Clear separation enables precise troubleshooting (e.g. isolating external LLM latency from database connection queue times) and enforces structured JSON formatting with `request_id` correlation.
* **Consequences**: Telemetry middleware and logging utilities must be consistently applied across all endpoints.
