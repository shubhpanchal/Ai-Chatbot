# API Contracts & Specification

## 1. Overview & General Conventions

The **AI Chat API** follows RESTful principles over HTTP/JSON with real-time token streaming provided via Server-Sent Events (SSE).

* **Base URL**: `/api/v1`
* **Authentication**: All `/api/v1` endpoints require an `Authorization` header:
  ```http
  Authorization: Bearer <API_KEY>
  ```
* **Idempotency**: Mutation endpoints accept an optional idempotency header to protect against duplicate execution on client retry:
  ```http
  Idempotency-Key: <unique-uuid-or-string>
  ```
* **Content Types**:
  * Standard endpoints: `application/json`
  * Streaming endpoints: `text/event-stream`

---

## 2. Standard Error Response Schema

All error responses adhere to a consistent JSON structure:

```json
{
  "error": {
    "code": "CONVERSATION_NOT_FOUND",
    "message": "Conversation with ID '018e3a2b-8a71-7000-8000-000000000001' not found.",
    "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "details": null
  }
}
```

### Standard Error Codes Dictionary

| Error Code | HTTP Status | Description |
| :--- | :--- | :--- |
| `UNAUTHORIZED` | `401 Unauthorized` | Missing, invalid, or inactive API key. |
| `FORBIDDEN` | `403 Forbidden` | Access to the requested action is prohibited. |
| `CONVERSATION_NOT_FOUND` | `404 Not Found` | Conversation does not exist, was deleted, or belongs to another API key. |
| `VALIDATION_ERROR` | `422 Unprocessable Entity` | Request payload failed Pydantic validation. |
| `RATE_LIMIT_EXCEEDED` | `429 Too Many Requests` | API key rate limit (100 req/min) exceeded. |
| `IDEMPOTENCY_CONFLICT` | `409 Conflict` | An identical request with this `Idempotency-Key` is currently in progress. |
| `LLM_TIMEOUT` | `504 Gateway Timeout` | Upstream LLM provider failed to respond within configured timeout. |
| `LLM_PROVIDER_ERROR` | `502 Bad Gateway` | Upstream LLM provider returned an unrecoverable error. |
| `SERVICE_UNAVAILABLE` | `503 Service Unavailable` | Critical dependency (PostgreSQL or Redis) failed readiness check. |
| `INTERNAL_SERVER_ERROR` | `500 Internal Server Error` | Unexpected unhandled server exception. |

---

## 3. Endpoints Specification

### 3.1 Create Conversation
* **Method**: `POST`
* **Path**: `/api/v1/conversations`
* **Summary**: Create a new conversation thread owned by the authenticated API key.

#### Request Body
```json
{
  "title": "Python Async Programming",
  "system_prompt": "You are an expert Python asyncio instructor."
}
```

#### Response: `201 Created`
```json
{
  "id": "018e3a2b-8a71-7000-8000-000000000001",
  "title": "Python Async Programming",
  "system_prompt": "You are an expert Python asyncio instructor.",
  "created_at": "2026-09-08T10:00:00Z",
  "updated_at": "2026-09-08T10:00:00Z"
}
```

---

### 3.2 List Conversations
* **Method**: `GET`
* **Path**: `/api/v1/conversations`
* **Summary**: List all active (non-deleted) conversations owned by the caller with pagination.

#### Query Parameters
* `page` (integer, optional, default: 1): Page number ($\ge 1$).
* `page_size` (integer, optional, default: 20, max: 100): Items per page.

#### Response: `200 OK`
```json
{
  "items": [
    {
      "id": "018e3a2b-8a71-7000-8000-000000000001",
      "title": "Python Async Programming",
      "system_prompt": "You are an expert Python asyncio instructor.",
      "created_at": "2026-09-08T10:00:00Z",
      "updated_at": "2026-09-08T10:05:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

---

### 3.3 Get Conversation Details
* **Method**: `GET`
* **Path**: `/api/v1/conversations/{conversation_id}`
* **Summary**: Retrieve a conversation thread including all messages, timestamps, and total token usage/cost summary.

#### Response: `200 OK`
```json
{
  "id": "018e3a2b-8a71-7000-8000-000000000001",
  "title": "Python Async Programming",
  "system_prompt": "You are an expert Python asyncio instructor.",
  "created_at": "2026-09-08T10:00:00Z",
  "updated_at": "2026-09-08T10:05:00Z",
  "messages": [
    {
      "id": "018e3a2b-8a71-7000-8000-000000000002",
      "role": "user",
      "content": "What is an event loop?",
      "created_at": "2026-09-08T10:01:00Z"
    },
    {
      "id": "018e3a2b-8a71-7000-8000-000000000003",
      "role": "assistant",
      "content": "An event loop is the core of every asyncio application...",
      "created_at": "2026-09-08T10:01:02Z"
    }
  ],
  "usage_summary": {
    "total_requests": 1,
    "total_tokens": 150,
    "estimated_cost_usd": 0.000045
  }
}
```

---

### 3.4 Soft Delete Conversation
* **Method**: `DELETE`
* **Path**: `/api/v1/conversations/{conversation_id}`
* **Summary**: Soft-delete a conversation thread.

#### Response: `204 No Content`
*(Empty response body)*

---

### 3.5 Send Message (Synchronous)
* **Method**: `POST`
* **Path**: `/api/v1/conversations/{conversation_id}/messages`
* **Summary**: Send a message, rebuild conversation context, execute LLM call, and return the complete assistant response.

#### Request Headers
* `Idempotency-Key` (string, optional): Unique key to guarantee idempotency on retry.

#### Request Body
```json
{
  "content": "Explain Python asyncio tasks in simple terms."
}
```

#### Response: `200 OK`
```json
{
  "id": "018e3a2b-8a71-7000-8000-000000000004",
  "conversation_id": "018e3a2b-8a71-7000-8000-000000000001",
  "role": "assistant",
  "content": "Tasks in asyncio are used to schedule coroutines concurrently...",
  "created_at": "2026-09-08T10:06:02Z",
  "usage": {
    "prompt_tokens": 85,
    "completion_tokens": 120,
    "total_tokens": 205,
    "estimated_cost_usd": 0.000062,
    "latency_ms": 780
  }
}
```

---

### 3.6 Send Message (Streaming SSE)
* **Method**: `POST`
* **Path**: `/api/v1/conversations/{conversation_id}/messages/stream`
* **Summary**: Stream the LLM response incrementally as Server-Sent Events.

#### Request Headers
* `Idempotency-Key` (string, optional): Unique key for request tracking.

#### Request Body
```json
{
  "content": "Write an example of asyncio.gather."
}
```

#### Response: `200 OK` (`text/event-stream`)
```text
event: token
data: {"token": "Here", "index": 0}

event: token
data: {"token": " is", "index": 1}

event: token
data: {"token": " an", "index": 2}

event: token
data: {"token": " example:", "index": 3}

event: done
data: {"message_id": "018e3a2b-8a71-7000-8000-000000000005", "total_tokens": 140, "estimated_cost_usd": 0.000042, "finish_reason": "stop"}
```

---

### 3.7 Liveness Probe
* **Method**: `GET`
* **Path**: `/health`
* **Summary**: Returns liveness status of the API process (no external dependency checks).

#### Response: `200 OK`
```json
{
  "status": "healthy",
  "timestamp": "2026-09-08T10:10:00Z"
}
```

---

### 3.8 Readiness Probe
* **Method**: `GET`
* **Path**: `/ready`
* **Summary**: Verifies connectivity to PostgreSQL and Redis.

#### Response: `200 OK`
```json
{
  "status": "ready",
  "checks": {
    "database": "connected",
    "redis": "connected",
    "llm_config": "valid"
  },
  "timestamp": "2026-09-08T10:10:00Z"
}
```
*(If a dependency is unreachable, returns `503 Service Unavailable` with diagnostic check results)*.
