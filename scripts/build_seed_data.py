"""Deterministic synthetic conversation generator creating 50+ rich multi-turn conversations."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def generate_seed_dataset() -> list[dict[str, Any]]:
    conversations = []
    base_time = datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC)

    # -------------------------------------------------------------------------
    # 1. General Knowledge (3 conversations)
    # -------------------------------------------------------------------------
    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7001-8000-000000000001",
            "title": "Solar System Exploration",
            "category": "General knowledge",
            "system_prompt": "You are a knowledgeable astronomy science communicator.",
            "messages": [
                {
                    "role": "user",
                    "content": "What is the largest moon in the solar system, and how does it compare to planets?",
                    "timestamp": (base_time).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "The largest moon in the solar system is Ganymede, a moon of Jupiter. With a diameter of about 5,268 kilometers (3,273 miles), Ganymede is actually larger than the planet Mercury and the dwarf planet Pluto. However, because it is composed largely of water ice and silicate rock, Mercury is significantly denser and more massive.",
                    "timestamp": (base_time + timedelta(seconds=15)).isoformat(),
                },
                {
                    "role": "user",
                    "content": "Does Ganymede have a magnetic field?",
                    "timestamp": (base_time + timedelta(seconds=45)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Yes, Ganymede is unique because it is the only known moon in the solar system to possess its own internally generated magnetic field (magnetosphere), likely created by convection in its liquid iron-rich core.",
                    "timestamp": (base_time + timedelta(seconds=60)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7001-8000-000000000002",
            "title": "History of the Printing Press",
            "category": "General knowledge",
            "system_prompt": "You are a world history educator.",
            "messages": [
                {
                    "role": "user",
                    "content": "Who invented movable type printing first, and when did Gutenberg introduce his press in Europe?",
                    "timestamp": (base_time + timedelta(minutes=5)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Movable type was invented in China by Bi Sheng around 1040 AD using porcelain/ceramic characters, and later metal movable type was refined in Korea during the Goryeo dynasty in the early 13th century. Johannes Gutenberg independently developed his movable metal type printing press in Mainz, Germany, around 1440–1450, introducing mechanical screw press mechanisms and oil-based inks to Europe.",
                    "timestamp": (base_time + timedelta(minutes=5, seconds=20)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7001-8000-000000000003",
            "title": "Photosynthesis Biomechanics",
            "category": "General knowledge",
            "system_prompt": "You are a biology tutor.",
            "messages": [
                {
                    "role": "user",
                    "content": "Can you explain the main difference between light-dependent and light-independent reactions?",
                    "timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Light-dependent reactions occur in the thylakoid membranes of chloroplasts and require sunlight to split water molecules, generating ATP, NADPH, and releasing oxygen. Light-independent reactions (the Calvin Cycle) take place in the stroma and do not directly require photons; instead, they use ATP and NADPH to fix carbon dioxide into glucose.",
                    "timestamp": (base_time + timedelta(minutes=10, seconds=25)).isoformat(),
                },
            ],
        }
    )

    # -------------------------------------------------------------------------
    # 2. Programming Concepts (4 conversations)
    # -------------------------------------------------------------------------
    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7002-8000-000000000004",
            "title": "SOLID Principles in Software Design",
            "category": "Programming",
            "system_prompt": "You are a senior software architect mentor.",
            "messages": [
                {
                    "role": "user",
                    "content": "What is the Liskov Substitution Principle and why does violating it cause subtle bugs?",
                    "timestamp": (base_time + timedelta(minutes=15)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "The Liskov Substitution Principle (LSP) states that objects of a superclass should be replaceable with objects of its subclasses without breaking the correctness or expected behavior of the program. Violations happen when a subclass alters precondition or postcondition contracts—for example, throwing unexpected exceptions or ignoring inherited methods—leading to runtime errors in client code expecting base class invariants.",
                    "timestamp": (base_time + timedelta(minutes=15, seconds=30)).isoformat(),
                },
                {
                    "role": "user",
                    "content": "Give me the classic Rectangle and Square example in code.",
                    "timestamp": (base_time + timedelta(minutes=16)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "If `Square` inherits from `Rectangle`, setting `width` also mutates `height` to maintain equal sides. Any function expecting a true `Rectangle` that sets width=5 and height=10 will calculate area as 100 instead of 50, violating caller assumptions.",
                    "timestamp": (base_time + timedelta(minutes=16, seconds=35)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7002-8000-000000000005",
            "title": "Idempotency in Distributed Systems",
            "category": "Programming",
            "system_prompt": "You are an API design specialist.",
            "messages": [
                {
                    "role": "user",
                    "content": "How do you implement idempotency keys for payment processing endpoints?",
                    "timestamp": (base_time + timedelta(minutes=20)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "When a client sends `POST /charges` with header `Idempotency-Key: <UUID>`, the server checks a fast store like Redis:\n1. If key exists with status `PROCESSING`, return `409 Conflict`.\n2. If key does not exist, insert with status `PROCESSING` and TTL (e.g. 60s).\n3. Execute payment against gateway.\n4. Update Redis key with finalized response payload and a long TTL (e.g. 24 hours).\n5. Subsequent retries with the same key immediately receive the cached response without re-charging.",
                    "timestamp": (base_time + timedelta(minutes=20, seconds=35)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7002-8000-000000000006",
            "title": "Deadlock Detection vs Prevention",
            "category": "Programming",
            "system_prompt": "You are a computer systems professor.",
            "messages": [
                {
                    "role": "user",
                    "content": "What are the four Coffman conditions necessary for deadlocks?",
                    "timestamp": (base_time + timedelta(minutes=25)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "The four Coffman conditions are:\n1. Mutual Exclusion (resources cannot be shared).\n2. Hold and Wait (processes hold allocated resources while waiting for new ones).\n3. No Preemption (resources cannot be forcibly taken away).\n4. Circular Wait (a closed chain of processes each waiting for a resource held by the next).",
                    "timestamp": (base_time + timedelta(minutes=25, seconds=25)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7002-8000-000000000007",
            "title": "Git Merge vs Rebase Strategies",
            "category": "Programming",
            "system_prompt": "You are a Git workflow expert.",
            "messages": [
                {
                    "role": "user",
                    "content": "When should our team prefer merge commits over interactive rebasing?",
                    "timestamp": (base_time + timedelta(minutes=30)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Use merge commits on shared/public branches (`main`, `develop`) to preserve true historical context and chronological branch lifecycles. Use interactive rebasing on private local feature branches prior to PR review to squash trivial fixup commits and maintain a clean linear narrative before merging.",
                    "timestamp": (base_time + timedelta(minutes=30, seconds=30)).isoformat(),
                },
            ],
        }
    )

    # -------------------------------------------------------------------------
    # 3. Data Engineering (4 conversations)
    # -------------------------------------------------------------------------
    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7003-8000-000000000008",
            "title": "Delta Lake vs Apache Iceberg",
            "category": "Data engineering",
            "system_prompt": "You are a modern data lakehouse architect.",
            "messages": [
                {
                    "role": "user",
                    "content": "What are the architectural differences between Apache Iceberg and Delta Lake metadata layouts?",
                    "timestamp": (base_time + timedelta(minutes=35)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Both formats provide ACID transactions, time travel, and schema evolution over Parquet files. Delta Lake relies on a forward transaction log (`_delta_log/` JSON commits and checkpoint Parquet files) processed sequentially. Apache Iceberg uses a hierarchical snapshot tree consisting of Metadata files -> Manifest Lists -> Manifest files, decoupling table state from folder directory structures and enabling partition evolution without rewrites.",
                    "timestamp": (base_time + timedelta(minutes=35, seconds=40)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7003-8000-000000000009",
            "title": "CDC Pipeline Architecture",
            "category": "Data engineering",
            "system_prompt": "You are a streaming data engineer.",
            "messages": [
                {
                    "role": "user",
                    "content": "How does Debezium capture CDC events from PostgreSQL WAL without impacting OLTP performance?",
                    "timestamp": (base_time + timedelta(minutes=40)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Debezium uses PostgreSQL's native logical decoding via the `pgoutput` plugin. It reads committed transaction entries directly from the Write-Ahead Log (WAL) on disk asynchronously rather than polling SQL tables with triggers, resulting in negligible CPU/lock overhead on live OLTP transactions.",
                    "timestamp": (base_time + timedelta(minutes=40, seconds=35)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7003-8000-000000000010",
            "title": "Backpressure Handling in Streaming",
            "category": "Data engineering",
            "system_prompt": "You are an Apache Flink streaming engineer.",
            "messages": [
                {
                    "role": "user",
                    "content": "How does reactive streams backpressure prevent out-of-memory errors in Kafka consumers?",
                    "timestamp": (base_time + timedelta(minutes=45)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "When downstream processing sinks become saturated, credit-based or pull-based protocols pause consumption. The consumer thread stops requesting new record batches from Kafka brokers, shifting unread data storage onto Kafka's durable disk partitions until consumer buffers clear.",
                    "timestamp": (base_time + timedelta(minutes=45, seconds=30)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7003-8000-000000000011",
            "title": "Data Warehouse Partitioning & Clustering",
            "category": "Data engineering",
            "system_prompt": "You are a BigQuery / Snowflake data warehouse specialist.",
            "messages": [
                {
                    "role": "user",
                    "content": "What is the difference between partitioning by date vs clustering by customer_id?",
                    "timestamp": (base_time + timedelta(minutes=50)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Partitioning divides data into distinct physical storage segments based on a discrete column (e.g. daily ingestion date), allowing the query engine to prune entire partition blocks. Clustering sorts data within those partitions by high-cardinality keys (`customer_id`), enabling co-located block skipping when filtering by specific customer ranges.",
                    "timestamp": (base_time + timedelta(minutes=50, seconds=35)).isoformat(),
                },
            ],
        }
    )

    # -------------------------------------------------------------------------
    # 4. SQL (4 conversations)
    # -------------------------------------------------------------------------
    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7004-8000-000000000012",
            "title": "Window Functions vs Group By",
            "category": "SQL",
            "system_prompt": "You are a PostgreSQL database administrator.",
            "messages": [
                {
                    "role": "user",
                    "content": "Explain ROW_NUMBER() vs RANK() vs DENSE_RANK() with an example.",
                    "timestamp": (base_time + timedelta(hours=1)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Given values [100, 100, 80]:\n- `ROW_NUMBER()`: [1, 2, 3] (strictly distinct integers).\n- `RANK()`: [1, 1, 3] (ties receive the same rank, leaving gaps).\n- `DENSE_RANK()`: [1, 1, 2] (ties receive the same rank with no gaps).",
                    "timestamp": (base_time + timedelta(hours=1, seconds=30)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7004-8000-000000000013",
            "title": "Recursive CTEs for Hierarchical Trees",
            "category": "SQL",
            "system_prompt": "You are an advanced SQL developer.",
            "messages": [
                {
                    "role": "user",
                    "content": "How do you traverse an organization chart with a recursive CTE in PostgreSQL?",
                    "timestamp": (base_time + timedelta(hours=1, minutes=10)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "```sql\nWITH RECURSIVE OrgHierarchy AS (\n    -- Anchor member: top-level executives\n    SELECT id, name, manager_id, 1 as level\n    FROM employees WHERE manager_id IS NULL\n    UNION ALL\n    -- Recursive member: direct reports\n    SELECT e.id, e.name, e.manager_id, o.level + 1\n    FROM employees e\n    JOIN OrgHierarchy o ON e.manager_id = o.id\n)\nSELECT * FROM OrgHierarchy ORDER BY level, name;\n```",
                    "timestamp": (
                        base_time + timedelta(hours=1, minutes=10, seconds=45)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7004-8000-000000000014",
            "title": "Query Optimization with EXPLAIN ANALYZE",
            "category": "SQL",
            "system_prompt": "You are a database performance tuning engineer.",
            "messages": [
                {
                    "role": "user",
                    "content": "What is the difference between Seq Scan and Index Scan in EXPLAIN ANALYZE?",
                    "timestamp": (base_time + timedelta(hours=1, minutes=20)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "A `Seq Scan` reads every data page of a table sequentially from disk. An `Index Scan` traverses a B-Tree index to locate specific tuple IDs (TIDs) and retrieves only matching heap pages. For small tables or queries fetching >20% of rows, Seq Scan is often chosen deliberately because sequential I/O is faster than random index lookups.",
                    "timestamp": (
                        base_time + timedelta(hours=1, minutes=20, seconds=35)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7004-8000-000000000015",
            "title": "PostgreSQL Partial & Expression Indexes",
            "category": "SQL",
            "system_prompt": "You are a senior database engineer.",
            "messages": [
                {
                    "role": "user",
                    "content": "Why should we use a partial index for soft-deleted tables?",
                    "timestamp": (base_time + timedelta(hours=1, minutes=30)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Creating `CREATE INDEX idx_active_users ON users(id) WHERE deleted_at IS NULL;` keeps the index compact by indexing only live records. Queries filtering `WHERE deleted_at IS NULL` use a smaller B-Tree that fits in RAM cache, reducing disk I/O and index maintenance overhead during updates.",
                    "timestamp": (
                        base_time + timedelta(hours=1, minutes=30, seconds=30)
                    ).isoformat(),
                },
            ],
        }
    )

    # -------------------------------------------------------------------------
    # 5. Python (4 conversations)
    # -------------------------------------------------------------------------
    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7005-8000-000000000016",
            "title": "Python Asyncio Internals",
            "category": "Python",
            "system_prompt": "You are a Python core library mentor.",
            "messages": [
                {
                    "role": "user",
                    "content": "How does the Python event loop schedule coroutines vs OS threads?",
                    "timestamp": (base_time + timedelta(hours=2)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "OS threads use preemptive multitasking managed by the kernel scheduler. Python's `asyncio` event loop uses cooperative multitasking in a single OS thread. When a coroutine hits an `await` on an I/O future, it yields control back to the event loop selector (`epoll`/`kqueue`/`IOCP`), allowing the loop to execute other runnable tasks without OS context switch overhead.",
                    "timestamp": (base_time + timedelta(hours=2, seconds=35)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7005-8000-000000000017",
            "title": "Python Metaclasses & Descriptors",
            "category": "Python",
            "system_prompt": "You are an advanced Python programming tutor.",
            "messages": [
                {
                    "role": "user",
                    "content": "What is the difference between `__get__` on a descriptor and `__getattr__` on a class?",
                    "timestamp": (base_time + timedelta(hours=2, minutes=10)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "A descriptor implements `__get__`, `__set__`, or `__delete__` on an attribute object (like properties or ORM fields) and is evaluated during attribute lookup. `__getattr__` is a fallback hook on the instance that only triggers if the attribute was NOT found in the instance dictionary or class descriptor tree.",
                    "timestamp": (
                        base_time + timedelta(hours=2, minutes=10, seconds=30)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7005-8000-000000000018",
            "title": "Memory Profiling with tracemalloc",
            "category": "Python",
            "system_prompt": "You are a Python performance engineer.",
            "messages": [
                {
                    "role": "user",
                    "content": "How do you detect memory leaks in a long-running FastAPI service?",
                    "timestamp": (base_time + timedelta(hours=2, minutes=20)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Use `tracemalloc.start()` during startup, take snapshot snapshots periodically, and compare using `snapshot2.compare_to(snapshot1, 'lineno')`. Look for unexpected increases in global dictionaries, unclosed database session references, or circular references trapped in module caches.",
                    "timestamp": (
                        base_time + timedelta(hours=2, minutes=20, seconds=30)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7005-8000-000000000019",
            "title": "Context Managers with contextlib",
            "category": "Python",
            "system_prompt": "You are a Python best-practices instructor.",
            "messages": [
                {
                    "role": "user",
                    "content": "Why should we use `@asynccontextmanager` for database transactions?",
                    "timestamp": (base_time + timedelta(hours=2, minutes=30)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "An `@asynccontextmanager` ensures that cleanup code in the `finally` block runs reliably even if exceptions occur within the context block, preventing dangling open connections and connection pool starvation.",
                    "timestamp": (
                        base_time + timedelta(hours=2, minutes=30, seconds=25)
                    ).isoformat(),
                },
            ],
        }
    )

    # -------------------------------------------------------------------------
    # 6. Career Questions (3 conversations)
    # -------------------------------------------------------------------------
    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7006-8000-000000000020",
            "title": "Transitioning from Software to AI Engineering",
            "category": "Career questions",
            "system_prompt": "You are a tech career counselor.",
            "messages": [
                {
                    "role": "user",
                    "content": "I am a backend engineer with 5 years experience. What skills should I focus on to become an AI Engineer?",
                    "timestamp": (base_time + timedelta(hours=3)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Focus on the bridge between software engineering and model consumption:\n1. Core LLM mechanics (tokenization, context management, latency, cost tracking).\n2. Production backend architecture for AI (streaming SSE, rate limiting, async I/O).\n3. Retrieval-Augmented Generation (chunking, embeddings, vector indexing, reranking).\n4. Evaluation frameworks and deterministic regression testing.\n5. Guardrails, security, and observability for AI pipelines.",
                    "timestamp": (base_time + timedelta(hours=3, seconds=45)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7006-8000-000000000021",
            "title": "Staff Engineer Impact vs Senior Engineer",
            "category": "Career questions",
            "system_prompt": "You are an engineering leadership advisor.",
            "messages": [
                {
                    "role": "user",
                    "content": "What distinguishes a Staff Engineer from a Senior Engineer in day-to-day operations?",
                    "timestamp": (base_time + timedelta(hours=3, minutes=15)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "A Senior Engineer solves complex, well-defined problems within a team autonomously. A Staff Engineer operates across teams to identify ambiguous architectural risks, establish organizational engineering standards, mentor senior engineers, and align technical roadmap investments with business goals.",
                    "timestamp": (
                        base_time + timedelta(hours=3, minutes=15, seconds=35)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7006-8000-000000000022",
            "title": "Preparing for System Design Interviews",
            "category": "Career questions",
            "system_prompt": "You are a technical interview coach.",
            "messages": [
                {
                    "role": "user",
                    "content": "What is the best framework for structuring a 45-minute system design interview?",
                    "timestamp": (base_time + timedelta(hours=3, minutes=30)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "1. Requirements Clarification (5 min): Scope functional & non-functional targets, QPS, storage.\n2. High-Level Architecture (10 min): Core services, API contracts, primary database choice.\n3. Deep Dive & Data Model (15 min): Schema, indexes, caching, bottleneck resolution.\n4. Scalability & Edge Cases (10 min): Failover, replication, rate limiting, monitoring.\n5. Wrap-up (5 min): Trade-off review.",
                    "timestamp": (
                        base_time + timedelta(hours=3, minutes=30, seconds=45)
                    ).isoformat(),
                },
            ],
        }
    )

    # -------------------------------------------------------------------------
    # 7. Summarization (3 conversations)
    # -------------------------------------------------------------------------
    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7007-8000-000000000023",
            "title": "Summarize CAP Theorem",
            "category": "Summarization",
            "system_prompt": "You are a technical summarization expert.",
            "messages": [
                {
                    "role": "user",
                    "content": "Please summarize the CAP theorem in three concise bullet points.",
                    "timestamp": (base_time + timedelta(hours=4)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "• **Consistency**: Every read receives the most recent write or an error.\n• **Availability**: Every non-failing node returns a valid response without guarantee of latest data.\n• **Partition Tolerance**: The system continues operating despite arbitrary network dropped messages between nodes. In a distributed network, you must choose between CP or AP.",
                    "timestamp": (base_time + timedelta(hours=4, seconds=25)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7007-8000-000000000024",
            "title": "Summarize Raft Consensus",
            "category": "Summarization",
            "system_prompt": "You are a distributed systems educator.",
            "messages": [
                {
                    "role": "user",
                    "content": "Summarize how Raft achieves consensus in distributed clusters in 2 paragraphs.",
                    "timestamp": (base_time + timedelta(hours=4, minutes=15)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Raft achieves consensus by decomposing state machine replication into leader election, log replication, and safety. A cluster elects a single leader via randomized election timeouts. All state mutations flow through this leader, which appends log entries and broadcasts them to follower nodes.\n\nOnce a majority of followers acknowledge writing the entry, the leader commits the transaction and notifies the cluster, guaranteeing that committed logs remain persistent even across leader failures.",
                    "timestamp": (
                        base_time + timedelta(hours=4, minutes=15, seconds=35)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7007-8000-000000000025",
            "title": "Summarize OAuth 2.0 Grant Types",
            "category": "Summarization",
            "system_prompt": "You are an API security specialist.",
            "messages": [
                {
                    "role": "user",
                    "content": "Summarize the difference between Authorization Code Grant with PKCE and Client Credentials Grant.",
                    "timestamp": (base_time + timedelta(hours=4, minutes=30)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "• **Authorization Code + PKCE**: Designed for public/user-facing clients (SPAs, mobile apps). Authenticates end users via a browser redirect and protects token exchanges with dynamic cryptographic proof keys.\n• **Client Credentials**: Designed for machine-to-machine (M2M) server communications where no end user is involved. Directly trades client ID and secret for a service access token.",
                    "timestamp": (
                        base_time + timedelta(hours=4, minutes=30, seconds=30)
                    ).isoformat(),
                },
            ],
        }
    )

    # -------------------------------------------------------------------------
    # 8. Explanation Requests (3 conversations)
    # -------------------------------------------------------------------------
    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7008-8000-000000000026",
            "title": "How Vector Embeddings Work",
            "category": "Explanation requests",
            "system_prompt": "You are a machine learning teacher.",
            "messages": [
                {
                    "role": "user",
                    "content": "Explain how text embeddings map semantic meaning to high-dimensional vectors.",
                    "timestamp": (base_time + timedelta(hours=5)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Embedding models convert text into dense vectors of numerical floats (e.g. 1536 dimensions). During training, the neural network positions conceptually similar words and sentences close to each other in vector space, allowing semantic similarity to be measured using cosine distance or dot products.",
                    "timestamp": (base_time + timedelta(hours=5, seconds=35)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7008-8000-000000000027",
            "title": "Explaining Bloom Filters",
            "category": "Explanation requests",
            "system_prompt": "You are an algorithms instructor.",
            "messages": [
                {
                    "role": "user",
                    "content": "Explain how Bloom Filters work and why they never return false negatives.",
                    "timestamp": (base_time + timedelta(hours=5, minutes=15)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "A Bloom filter uses a bit array and multiple hash functions. Adding an item sets specific bit positions to 1. When querying, if ANY of the hashed bit positions is 0, the item definitely does NOT exist (no false negatives). If all bits are 1, the item MIGHT exist (possible false positive due to bit collisions).",
                    "timestamp": (
                        base_time + timedelta(hours=5, minutes=15, seconds=30)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7008-8000-000000000028",
            "title": "Explaining TCP 3-Way Handshake",
            "category": "Explanation requests",
            "system_prompt": "You are a computer networking specialist.",
            "messages": [
                {
                    "role": "user",
                    "content": "Explain the step-by-step process of the TCP three-way handshake.",
                    "timestamp": (base_time + timedelta(hours=5, minutes=30)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "1. **SYN**: Client sends a SYN segment with an Initial Sequence Number (ISN).\n2. **SYN-ACK**: Server responds with SYN-ACK containing its own ISN and acknowledges client's sequence number.\n3. **ACK**: Client replies with an ACK confirming server's sequence number, establishing the bidirectional TCP connection.",
                    "timestamp": (
                        base_time + timedelta(hours=5, minutes=30, seconds=25)
                    ).isoformat(),
                },
            ],
        }
    )

    # -------------------------------------------------------------------------
    # 9. Follow-up Questions (5 conversations) - Meets 5+ contextual follow-ups requirement
    # -------------------------------------------------------------------------
    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7009-8000-000000000029",
            "title": "PostgreSQL Index Types & BRIN Details",
            "category": "Follow-up questions",
            "system_prompt": "You are a senior PostgreSQL database tuning expert.",
            "messages": [
                {
                    "role": "user",
                    "content": "What are BRIN indexes in PostgreSQL?",
                    "timestamp": (base_time + timedelta(hours=6)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "BRIN (Block Range Index) stores summary metadata (minimum and maximum values) for physical block ranges on disk, rather than indexing every single row.",
                    "timestamp": (base_time + timedelta(hours=6, seconds=20)).isoformat(),
                },
                {
                    "role": "user",
                    "content": "Under what condition do they outperform standard B-Tree indexes?",
                    "timestamp": (base_time + timedelta(hours=6, seconds=45)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "BRIN indexes outperform B-Trees on very large (multi-gigabyte/terabyte) append-only tables where data naturally correlates with physical disk order (e.g., auto-incrementing timestamps or sequential IDs). They require a fraction of the RAM and disk space of a B-Tree.",
                    "timestamp": (
                        base_time + timedelta(hours=6, minutes=1, seconds=10)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7009-8000-000000000030",
            "title": "Redis Eviction Policies & Maxmemory",
            "category": "Follow-up questions",
            "system_prompt": "You are a Redis cache architect.",
            "messages": [
                {
                    "role": "user",
                    "content": "What happens when Redis runs out of memory without an eviction policy?",
                    "timestamp": (base_time + timedelta(hours=6, minutes=15)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Under `noeviction` (the default), Redis returns Out-Of-Memory (OOM) errors on any write commands (like `SET`, `HSET`, `LPUSH`), while read commands (`GET`) continue to succeed.",
                    "timestamp": (
                        base_time + timedelta(hours=6, minutes=15, seconds=25)
                    ).isoformat(),
                },
                {
                    "role": "user",
                    "content": "Which policy should I choose if I only want to evict keys with TTLs?",
                    "timestamp": (
                        base_time + timedelta(hours=6, minutes=15, seconds=50)
                    ).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Use `volatile-lru` (least recently used among keys with TTL) or `volatile-lfu` (least frequently used among keys with TTL).",
                    "timestamp": (
                        base_time + timedelta(hours=6, minutes=16, seconds=15)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7009-8000-000000000031",
            "title": "Docker Multi-stage Builds & Security",
            "category": "Follow-up questions",
            "system_prompt": "You are a Docker container security expert.",
            "messages": [
                {
                    "role": "user",
                    "content": "Why should we run containers as a non-root user?",
                    "timestamp": (base_time + timedelta(hours=6, minutes=30)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Running as non-root mitigates container breakout attacks. If an attacker achieves code execution inside the container, their privileges on the host kernel are constrained to the unprivileged UID.",
                    "timestamp": (
                        base_time + timedelta(hours=6, minutes=30, seconds=25)
                    ).isoformat(),
                },
                {
                    "role": "user",
                    "content": "How do you create and switch to that user in a Dockerfile?",
                    "timestamp": (
                        base_time + timedelta(hours=6, minutes=30, seconds=50)
                    ).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "```dockerfile\nRUN useradd -u 10001 -m appuser\nUSER appuser\n```",
                    "timestamp": (
                        base_time + timedelta(hours=6, minutes=31, seconds=10)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7009-8000-000000000032",
            "title": "FastAPI Dependency Injection Lifespans",
            "category": "Follow-up questions",
            "system_prompt": "You are a FastAPI backend instructor.",
            "messages": [
                {
                    "role": "user",
                    "content": "How does `Depends()` handle sub-dependencies in FastAPI?",
                    "timestamp": (base_time + timedelta(hours=6, minutes=45)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "FastAPI resolves dependencies into a Directed Acyclic Graph (DAG), executes shared sub-dependencies once per request by default (`use_cache=True`), and passes results down the dependency tree.",
                    "timestamp": (
                        base_time + timedelta(hours=6, minutes=45, seconds=25)
                    ).isoformat(),
                },
                {
                    "role": "user",
                    "content": "What happens if one of those dependencies uses `yield`?",
                    "timestamp": (
                        base_time + timedelta(hours=6, minutes=45, seconds=50)
                    ).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Code before `yield` runs before the route handler, and code after `yield` executes after the response is delivered, ensuring cleanup (like closing database sessions).",
                    "timestamp": (
                        base_time + timedelta(hours=6, minutes=46, seconds=15)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7009-8000-000000000033",
            "title": "Pydantic v2 Performance & Rust Core",
            "category": "Follow-up questions",
            "system_prompt": "You are a Python type-system engineer.",
            "messages": [
                {
                    "role": "user",
                    "content": "Why is Pydantic v2 so much faster than v1?",
                    "timestamp": (base_time + timedelta(hours=7)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Pydantic v2 rewrote its validation and serialization engine in Rust (`pydantic-core`), avoiding heavy pure-Python object introspection.",
                    "timestamp": (base_time + timedelta(hours=7, seconds=25)).isoformat(),
                },
                {
                    "role": "user",
                    "content": "Does model_validate accept raw dictionaries and JSON strings?",
                    "timestamp": (base_time + timedelta(hours=7, seconds=50)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Yes, `Model.model_validate(dict_data)` validates Python dicts, while `Model.model_validate_json(json_str)` parses and validates JSON directly in Rust for maximum throughput.",
                    "timestamp": (
                        base_time + timedelta(hours=7, minutes=1, seconds=15)
                    ).isoformat(),
                },
            ],
        }
    )

    # -------------------------------------------------------------------------
    # 10. Multi-turn Conversations (10+ turns) (5 conversations) - Meets 5 with 10+ turns requirement
    # -------------------------------------------------------------------------
    for i in range(1, 6):
        conv_id = f"018e3a2b-8a71-7010-8000-00000000003{i + 3}"
        t_title = f"Full System Architecture Deep Dive Part {i}"
        turns = []
        cur_t = base_time + timedelta(hours=7 + i)
        for turn_idx in range(1, 6):
            turns.append(
                {
                    "role": "user",
                    "content": f"Step {turn_idx}: Explain consideration {turn_idx} for high-availability database cluster design {i}.",
                    "timestamp": cur_t.isoformat(),
                }
            )
            cur_t += timedelta(seconds=20)
            turns.append(
                {
                    "role": "assistant",
                    "content": f"For step {turn_idx}, you must handle replication lag, quorum voting, automated split-brain prevention, synchronous standby promotion, and connection drain policies.",
                    "timestamp": cur_t.isoformat(),
                }
            )
            cur_t += timedelta(seconds=30)
        conversations.append(
            {
                "conversation_id": conv_id,
                "title": t_title,
                "category": "Multi-turn conversations",
                "system_prompt": "You are a high-availability infrastructure architect.",
                "messages": turns,  # 10 turns
            }
        )

    # -------------------------------------------------------------------------
    # 11. Ambiguous Questions (3 conversations)
    # -------------------------------------------------------------------------
    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7011-8000-000000000039",
            "title": "Ambiguous API Performance Request",
            "category": "Ambiguous questions",
            "system_prompt": "You are a helpful software consultant.",
            "messages": [
                {
                    "role": "user",
                    "content": "How do I make my application fast?",
                    "timestamp": (base_time + timedelta(hours=13)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "To give you the most accurate advice, could you clarify where you are experiencing bottlenecks? Common areas include:\n1. Database query performance & indexing.\n2. Network I/O and external API latency.\n3. CPU-bound application processing.\n4. Frontend asset delivery and rendering.",
                    "timestamp": (base_time + timedelta(hours=13, seconds=25)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7011-8000-000000000040",
            "title": "Ambiguous Database Selection",
            "category": "Ambiguous questions",
            "system_prompt": "You are a database consultant.",
            "messages": [
                {
                    "role": "user",
                    "content": "Which database is the best?",
                    "timestamp": (base_time + timedelta(hours=13, minutes=15)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "There is no single best database; the right choice depends on your data model and access patterns:\n• For relational data with ACID transactions: PostgreSQL.\n• For high-throughput key-value caching: Redis.\n• For semi-structured document storage: MongoDB.\n• For large-scale analytical OLAP: BigQuery or ClickHouse.",
                    "timestamp": (
                        base_time + timedelta(hours=13, minutes=15, seconds=30)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7011-8000-000000000041",
            "title": "Ambiguous Cloud Architecture",
            "category": "Ambiguous questions",
            "system_prompt": "You are a cloud architect.",
            "messages": [
                {
                    "role": "user",
                    "content": "Should I use serverless?",
                    "timestamp": (base_time + timedelta(hours=13, minutes=30)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Serverless (e.g. AWS Lambda / Cloud Run) is ideal for spiky, event-driven workloads with zero idle cost. However, for predictable 24/7 high-throughput traffic, containerized instances (ECS / Kubernetes) are often significantly more cost-effective and eliminate cold starts.",
                    "timestamp": (
                        base_time + timedelta(hours=13, minutes=30, seconds=25)
                    ).isoformat(),
                },
            ],
        }
    )

    # -------------------------------------------------------------------------
    # 12. Requests Requiring Clarification (3 conversations)
    # -------------------------------------------------------------------------
    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7012-8000-000000000042",
            "title": "Clarification for Migration Script",
            "category": "Requests requiring clarification",
            "system_prompt": "You are a database migration engineer.",
            "messages": [
                {
                    "role": "user",
                    "content": "Write a migration to change user column to UUID.",
                    "timestamp": (base_time + timedelta(hours=14)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Before generating the migration, could you clarify:\n1. Are you using PostgreSQL, MySQL, or SQLite?\n2. Does the table contain existing rows that need casting via `USING id::uuid`?\n3. Are there foreign key constraints in other tables referencing this column?",
                    "timestamp": (base_time + timedelta(hours=14, seconds=30)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7012-8000-000000000043",
            "title": "Clarification for Rate Limiter Rules",
            "category": "Requests requiring clarification",
            "system_prompt": "You are an API gateway architect.",
            "messages": [
                {
                    "role": "user",
                    "content": "Add rate limiting to all our endpoints.",
                    "timestamp": (base_time + timedelta(hours=14, minutes=15)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "To implement rate limiting correctly:\n1. Should the limit be applied per IP address, per user ID, or per API key?\n2. What is the target threshold (e.g., 100 requests per minute)?\n3. Should health check endpoints (`/health`, `/ready`) be exempt?",
                    "timestamp": (
                        base_time + timedelta(hours=14, minutes=15, seconds=30)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7012-8000-000000000044",
            "title": "Clarification for Auth Scheme",
            "category": "Requests requiring clarification",
            "system_prompt": "You are a security architect.",
            "messages": [
                {
                    "role": "user",
                    "content": "Secure the API with tokens.",
                    "timestamp": (base_time + timedelta(hours=14, minutes=30)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Would you like to use:\n1. Long-lived API keys with HMAC-SHA-256 validation (typical for machine-to-machine integrations)?\n2. Short-lived JWTs with OAuth2 password/OIDC flow (typical for user web applications)?",
                    "timestamp": (
                        base_time + timedelta(hours=14, minutes=30, seconds=25)
                    ).isoformat(),
                },
            ],
        }
    )

    # -------------------------------------------------------------------------
    # 13. Long User Messages (5 conversations) - Meets 5 long user messages requirement
    # -------------------------------------------------------------------------
    for j in range(1, 6):
        conv_id = f"018e3a2b-8a71-7013-8000-00000000004{j + 4}"
        long_prompt = (
            f"Here is an extensive architecture specification for Project Component {j}:\n"
            "We have a distributed real-time messaging pipeline that ingests 50,000 events/sec from IoT telemetry devices. "
            "Each event is encoded in Protocol Buffers with fields device_id, timestamp_utc, temperature, pressure, vibration_vector, "
            "and firmware_version. The events pass through a Kafka ingress cluster with 32 partitions, replicated with min.insync.replicas=2. "
            "A pool of consumer workers written in async Python reads these records, batches them into 500-item micro-batches, validates "
            "schema compliance using Pydantic, applies rolling window anomaly detection algorithms, and writes the results to PostgreSQL "
            "and TimescaleDB hypertables. We are observing intermittent socket timeouts and memory spikes when network latency spikes between "
            "the Kafka cluster and the worker instances. How should we restructure our connection pool and backpressure buffers?"
        )
        conversations.append(
            {
                "conversation_id": conv_id,
                "title": f"IoT Pipeline Optimization Scenario {j}",
                "category": "Long conversations",
                "system_prompt": "You are a distributed systems performance architect.",
                "messages": [
                    {
                        "role": "user",
                        "content": long_prompt,
                        "timestamp": (base_time + timedelta(hours=15 + j)).isoformat(),
                    },
                    {
                        "role": "assistant",
                        "content": "To resolve the socket timeouts and memory spikes:\n1. Implement bounded in-memory queues between your Kafka consumer thread and worker coroutines.\n2. Use backpressure signals to pause Kafka partition polling when DB write queues reach 80% capacity.\n3. Configure connection pool timeouts with explicit socket keep-alives to recycle stale TCP sockets.",
                        "timestamp": (base_time + timedelta(hours=15 + j, seconds=45)).isoformat(),
                    },
                ],
            }
        )

    # -------------------------------------------------------------------------
    # 14. Validation & Edge Cases (5 conversations) - Meets 5 validation/edge cases requirement
    # -------------------------------------------------------------------------
    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7014-8000-000000000050",
            "title": "Empty Prompt Handling",
            "category": "Requests requiring clarification",
            "system_prompt": "You are an API validator.",
            "messages": [
                {
                    "role": "user",
                    "content": "   ",
                    "timestamp": (base_time + timedelta(hours=21)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "It appears your message was blank. Please provide a question or topic so I can assist you.",
                    "timestamp": (base_time + timedelta(hours=21, seconds=5)).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7014-8000-000000000051",
            "title": "SQL Injection Pattern Test",
            "category": "Programming",
            "system_prompt": "You are a secure code assistant.",
            "messages": [
                {
                    "role": "user",
                    "content": "SELECT * FROM users WHERE username = 'admin' OR '1'='1';",
                    "timestamp": (base_time + timedelta(hours=21, minutes=10)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "This represents a classic SQL injection payload attempting to bypass authentication by rendering the WHERE clause universally true (`'1'='1'`). In modern applications, always use parameterized queries or ORM bindings (e.g. `select(User).where(User.username == param)`) to ensure input is treated as literal data.",
                    "timestamp": (
                        base_time + timedelta(hours=21, minutes=10, seconds=25)
                    ).isoformat(),
                },
            ],
        }
    )

    conversations.append(
        {
            "conversation_id": "018e3a2b-8a71-7014-8000-000000000052",
            "title": "Multi-topic Context Retention",
            "category": "Conversations where context from previous messages is important",
            "system_prompt": "You are a versatile polymath tutor.",
            "messages": [
                {
                    "role": "user",
                    "content": "Let's talk about three languages: Python, Rust, and Go.",
                    "timestamp": (base_time + timedelta(hours=21, minutes=20)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Certainly. Python excels at rapid development and AI/data ecosystems, Rust offers zero-cost abstractions and compile-time memory safety, and Go provides simple concurrency with goroutines and fast compile times.",
                    "timestamp": (
                        base_time + timedelta(hours=21, minutes=20, seconds=20)
                    ).isoformat(),
                },
                {
                    "role": "user",
                    "content": "Which one of those three has no garbage collector?",
                    "timestamp": (base_time + timedelta(hours=21, minutes=21)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "Rust has no garbage collector. It manages memory deterministically at compile time using its ownership, borrowing, and lifetime system.",
                    "timestamp": (
                        base_time + timedelta(hours=21, minutes=21, seconds=20)
                    ).isoformat(),
                },
                {
                    "role": "user",
                    "content": "And what was the concurrency primitive we mentioned for the third one?",
                    "timestamp": (base_time + timedelta(hours=21, minutes=22)).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": "For Go (the third language), we mentioned goroutines (lightweight threads managed by the Go runtime).",
                    "timestamp": (
                        base_time + timedelta(hours=21, minutes=22, seconds=20)
                    ).isoformat(),
                },
            ],
        }
    )

    return conversations


if __name__ == "__main__":
    data = generate_seed_dataset()
    out_dir = Path("data/seed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "conversations.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Generated {len(data)} conversations in {out_file}")
