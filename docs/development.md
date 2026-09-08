# Development, Testing & Operations Guide

## 1. Prerequisites

* **Python**: 3.12+
* **Docker & Docker Compose**: Docker 24+ and Compose v2+
* **Git**: 2.40+
* **OpenAI API Key**: Required for live model testing (optional for automated mocked test suites)

---

## 2. Local Environment Setup

### 2.1 Virtual Environment Setup
```bash
# 1. Create a virtual environment
python -m venv .venv

# 2. Activate the virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 3. Install dependencies in editable mode with development tools
pip install -e ".[dev]"
```

### 2.2 Environment Configuration
Copy the sample environment file:
```bash
cp .env.example .env
```

Configure your local `.env` values:
```env
APP_ENV=development
LOG_LEVEL=DEBUG

# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_chat_db
DB_CONNECT_TIMEOUT_SECONDS=5
DB_COMMAND_TIMEOUT_SECONDS=10

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_SOCKET_TIMEOUT_SECONDS=2

# Security & Secrets
API_KEY_SECRET=your-super-secret-pepper-key-minimum-32-chars-long

# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_OUTPUT_TOKENS=2048
OPENAI_TIMEOUT_SECONDS=30

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
```

---

## 3. Running with Docker Compose

The fastest way to launch the full stack (API + PostgreSQL + Redis) without manual local database installation:

```bash
# Build and launch all services
docker compose up --build

# Run in detached mode
docker compose up -d

# View live application logs
docker compose logs -f api

# Stop all services and retain persistent database volumes
docker compose down

# Stop and wipe persistent database volumes
docker compose down -v
```

---

## 4. Database Migrations & Seeding

### 4.1 Applying Alembic Migrations
```bash
# Run all pending migrations
alembic upgrade head

# Generate a new migration after updating models
alembic revision --autogenerate -m "add new column"

# Rollback one migration step
alembic downgrade -1
```

### 4.2 Generating an API Key
Generate an API key with HMAC hashing and write it to the database:
```bash
python scripts/create_api_key.py --name "development-key"
```
*Output:*
```text
Created API Key successfully!
Key Name : development-key
Raw Key  : ak_dev_9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c
NOTE: Save this raw key securely. It will never be displayed again.
```

### 4.3 Seeding the Database
Load the 50+ multi-turn synthetic conversation dataset:
```bash
python scripts/seed_db.py --api-key "ak_dev_9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c"
```

---

## 5. Testing & Code Quality

### 5.1 Running the Automated Test Suite
The test suite utilizes `MockLLMProvider` by default to run instantly at zero cost:
```bash
# Run all unit and integration tests
pytest

# Run with verbose output and coverage report
pytest -v --cov=app --cov-report=term-missing

# Run only unit tests
pytest tests/unit

# Run only integration tests
pytest tests/integration
```

### 5.2 Running the Deterministic Evaluation Suite
```bash
python scripts/run_evals.py
```

### 5.3 Static Code Analysis & Linting
```bash
# Check code style with Ruff
ruff check .

# Format code with Ruff
ruff format .

# Strict type checking with mypy
mypy app
```

---

## 6. Git Workflow & Branching Conventions

* **Branching Model**:
  * `main`: Production-ready, stable releases only.
  * `develop`: Active integration branch.
  * `feature/<feature-name>`: Feature branch created off `develop`.
  * `fix/<bug-name>`: Bug fix branch created off `develop`.
* **Commit Conventions**:
  Follow Conventional Commits:
  ```text
  feat: add Redis-backed sliding-window rate limiter
  fix: handle mid-stream client disconnect gracefully
  test: add cross-API-key tenant authorization tests
  docs: update API contracts for SSE streaming
  chore: configure multi-stage Dockerfile
  ```
