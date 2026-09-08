# Synthetic Conversation Seed Dataset

## 1. Dataset Overview

This dataset provides a defined synthetic conversation corpus used for development, testing, database seeding, and deterministic evaluations. It does **NOT** contain real personal identifiable information (PII) and is **NOT** used for ML model training.

* **File Location**: `data/seed/conversations.json`
* **Total Conversations**: 52
* **Total Messages**: 142+
* **Format**: JSON array of conversation objects.

---

## 2. Data Structure

Each conversation adheres to the following schema:

```json
{
  "conversation_id": "018e3a2b-8a71-7001-8000-000000000001",
  "title": "Solar System Exploration",
  "category": "General knowledge",
  "system_prompt": "You are a knowledgeable astronomy science communicator.",
  "messages": [
    {
      "role": "user",
      "content": "What is the largest moon in the solar system...?",
      "timestamp": "2026-09-01T10:00:00Z"
    },
    {
      "role": "assistant",
      "content": "The largest moon in the solar system is Ganymede...",
      "timestamp": "2026-09-01T10:00:15Z"
    }
  ]
}
```

---

## 3. Category Distribution

The dataset spans the 15 required domain categories:

1. **General Knowledge**: Astronomy, printing press history, cellular biology.
2. **Programming**: SOLID principles, distributed idempotency keys, deadlock conditions, git workflows.
3. **Data Engineering**: Apache Iceberg vs Delta Lake, CDC via PostgreSQL WAL, backpressure handling, partitioning vs clustering.
4. **SQL**: Window functions (RANK/DENSE_RANK), recursive CTEs, query optimization with EXPLAIN ANALYZE, partial indexes.
5. **Python**: Asyncio event loops, metaclasses vs descriptors, memory leak profiling with tracemalloc, async context managers.
6. **Career Questions**: Transitioning to AI Engineering, Staff vs Senior impact, System Design interview frameworks.
7. **Summarization**: CAP theorem summaries, Raft consensus mechanism, OAuth 2.0 grant types.
8. **Explanation Requests**: Vector embeddings, Bloom filters, TCP 3-way handshake.
9. **Follow-up Questions**: Multi-turn technical explorations on PostgreSQL BRIN indexes, Redis eviction policies, Docker security, FastAPI dependency injection, and Pydantic v2 internals.
10. **Multi-turn Conversations (10+ turns)**: 5 comprehensive deep-dive architecture discussions spanning 10 turns each.
11. **Ambiguous Questions**: Open-ended queries prompting clarification on performance, database selection, and cloud architecture.
12. **Requests Requiring Clarification**: Requests missing parameters (migration target dialect, rate limiter scope, auth scheme).
13. **Long Conversations**: Scenarios containing intentionally long user prompt payloads (IoT streaming telemetry pipeline architectures).
14. **Conversations Containing Multiple Topics**: Multi-language comparisons (Python, Rust, Go).
15. **Context Retention**: Dialogues testing cross-turn entity references and contextual follow-ups.

---

## 4. Seeding the Database

To seed this dataset into PostgreSQL:

```bash
# Seed with auto-generated dev key
python scripts/seed_db.py

# Seed with a designated API key
python scripts/seed_db.py --api-key "ak_dev_your_key_here"
```
