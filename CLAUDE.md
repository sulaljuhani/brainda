# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VIB is a personal knowledge management system combining note-taking, document ingestion, semantic search, RAG chat, smart reminders, and calendar scheduling. It's a microservices architecture running on Docker Compose with 8 development stages (Stage 0-8) testing progressive features.

## Architecture

### Service Components

The application uses **container-based service selection** via `entrypoint.sh`:
- If `SERVICE=worker`: Runs Celery worker (`celery -A worker.tasks worker`)
- If `SERVICE=beat`: Runs Celery beat scheduler (`celery -A worker.tasks beat`)
- Otherwise: Runs FastAPI orchestrator (`uvicorn api.main:app`)

**6 Docker services** defined in `docker-compose.yml`:
1. **orchestrator** (vib-orchestrator): FastAPI API server on port 8000
2. **worker** (vib-worker): Celery background task processor
3. **beat** (vib-beat): Celery beat scheduler for periodic tasks
4. **postgres** (vib-postgres): PostgreSQL 15 database on port 5434
5. **redis** (vib-redis): Redis 7 message broker/cache on port 6379
6. **qdrant** (vib-qdrant): Vector database on port 6333

### Critical Volumes

- `./vault:/vault` - Mounted in both orchestrator and worker for markdown note files
- `./uploads:/app/uploads` - Document upload storage
- `./migrations:/app/migrations` - SQL migration files auto-applied on startup

### Code Entry Points

- **API**: `app/api/main.py` - FastAPI application with lifespan for migrations, scheduler startup, and Qdrant collection initialization
- **Worker**: `app/worker/tasks.py` - Celery tasks for embeddings, document ingestion, Google Calendar sync, and cleanup
- **Scheduler**: `app/worker/scheduler.py` - APScheduler integration for time-based reminder firing
- **Container**: `entrypoint.sh` - Service selector based on `SERVICE` environment variable

## Commands

### Building and Running

```bash
# Start all services (production mode)
docker compose up -d

# Rebuild specific service after code changes
docker compose up -d --build orchestrator
docker compose up -d --build worker

# View logs
docker compose logs -f orchestrator
docker compose logs -f worker

# Stop all services
docker compose down
```

### Development Mode (Hot Reload)

```bash
# Start infrastructure only
docker compose up -d postgres redis qdrant

# Run API with hot reload
cd app
export PYTHONPATH=$(pwd)
export DATABASE_URL="postgresql://vib:<password>@localhost:5434/vib"
export REDIS_URL="redis://localhost:6379/0"
export QDRANT_URL="http://localhost:6333"
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Run Celery worker (separate terminal)
celery -A worker.tasks worker --loglevel=info

# Run Celery beat (separate terminal)
celery -A worker.tasks beat --loglevel=info
```

### Testing

**Test Prerequisites**: `jq`, `curl`, `docker`, `python3` or `bc`

```bash
# Run all 8 stages of integration tests
./tests/stage_runner.sh --all --verbose

# Run specific stage
./tests/stage_runner.sh --stage 1 --verbose

# Available stages:
# Stage 0: Health and metrics
# Stage 1: Notes + vector search
# Stage 2: Reminders + scheduler
# Stage 3: Documents + RAG
# Stage 4: Metrics validation
# Stage 5: Idempotency
# Stage 6: Calendar events + RRULE
# Stage 7: Google Calendar sync
# Stage 8: Multi-user auth (passkeys + TOTP)
```

Tests use bash scripts in `tests/` with shared utilities in `tests/common.sh`. Each test creates temporary directories under `/tmp/vib-test-*`.

### Database Operations

```bash
# Access PostgreSQL
docker exec -it vib-postgres psql -U vib -d vib

# Run migration manually
docker exec vib-postgres psql -U vib -d vib -f /app/migrations/006_add_multi_user_auth.sql

# Query examples
docker exec vib-postgres psql -U vib -d vib -c "SELECT COUNT(*) FROM notes;"
docker exec vib-postgres psql -U vib -d vib -c "SELECT * FROM file_sync_state LIMIT 5;"
```

### Debugging

```bash
# Check Redis queue depth
docker exec vib-redis redis-cli LLEN celery

# Check Qdrant collections
curl http://localhost:6333/collections

# Check health endpoint
curl http://localhost:8000/api/v1/health

# Check Prometheus metrics
curl http://localhost:8000/api/v1/metrics

# Watch Celery tasks
docker compose logs -f worker | grep task_id
```

## Architecture Deep Dive

### Request Flow

**API Request Flow (LIFO middleware chain)**:
```
Request
  → MetricsMiddleware (observes duration/status)
  → IdempotencyMiddleware (deduplicates POST/PUT/PATCH)
  → Auth Dependency (validates session/API token)
  → CORSMiddleware (handles preflight)
  → Router (notes, reminders, calendar, etc.)
  → Service Layer (business logic)
  → Database (asyncpg connection pool)
```

**Background Task Flow**:
```
API endpoint
  → Queue Celery task via Redis
  → Worker picks up task
  → Task processes (embedding, ingestion, sync)
  → Updates database
  → Publishes to Qdrant (vector DB)
```

### File Watcher System

**Critical Implementation Note**: The file watcher uses `PollingObserver` (not `Observer`) for cross-platform compatibility, especially Docker on Windows where inotify events don't propagate properly.

Location: `app/worker/tasks.py` lines 567-618

```python
# VaultWatcher monitors /vault for .md file changes
# Uses 5-second debounce to avoid duplicate embedding tasks
observer = PollingObserver(timeout=1)  # Poll every 1 second
observer.schedule(event_handler, "/vault", recursive=True)
```

**Flow**:
1. File modified in `/vault/*.md`
2. `VaultWatcher.on_modified()` detects change after 5s debounce
3. Queues `schedule_embedding_check` task
4. Task verifies content changed (SHA-256 hash comparison)
5. Extracts note_id from frontmatter
6. Queues `embed_note_task`
7. Updates `file_sync_state.last_embedded_at` timestamp

### Database Schema

**Critical Tables**:
- `users` - Multi-user support (Stage 8)
- `sessions` - Session tokens (30-day expiry)
- `passkey_credentials` - WebAuthn credential storage
- `notes` - User notes with unique constraint on (user_id, title)
- `file_sync_state` - Tracks embedding state for vault markdown files
- `documents` - Uploaded documents with SHA-256 deduplication
- `reminders` - Time-based reminders with RRULE support
- `calendar_events` - Calendar events with RRULE expansion
- `idempotency_keys` - Exactly-once semantics (24h TTL)
- `google_calendar_tokens` - Encrypted OAuth tokens for Google Calendar sync

**Critical Indexes**:
- All tables have `user_id` indexes for user isolation
- `file_sync_state.file_path` has unique constraint per user
- `documents.content_hash` for deduplication
- `reminders.due_at_utc` for scheduler queries

### Embedding Pipeline

**Model**: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)

**Service**: `app/api/services/embedding_service.py`

**Flow**:
1. Content extracted (notes, documents)
2. `EmbeddingService.create_embeddings()` generates vector
3. `VectorService.upsert()` stores in Qdrant with metadata
4. Search uses cosine similarity with user_id filter

**Qdrant Collections**:
- Collection name: `vib_embeddings`
- Vector size: 384
- Distance: Cosine
- Payload: `{user_id, content_type, title, body, created_at}`

### Middleware Architecture

**Idempotency Middleware** (`app/api/middleware/idempotency.py`):
- Intercepts POST/PUT/PATCH with `Idempotency-Key` header
- Stores request hash + response in Redis (24h TTL)
- Returns cached response for duplicate requests
- Critical for reminder/note deduplication

**Metrics Middleware**:
- Measures `api_request_duration_seconds` histogram
- Labels: method, endpoint, status_code
- Prometheus metrics exposed at `/api/v1/metrics`

**Auth Dependency** (`app/api/dependencies.py`):
- Validates Bearer token (session token or legacy API token)
- Returns `user_id` UUID
- Raises 401 if invalid

### Background Tasks

**Celery Configuration** (`app/worker/tasks.py`):
- Task time limit: 900s (hard), 840s (soft)
- Worker concurrency: 3 (configurable via `CELERY_WORKER_CONCURRENCY`)
- Prefetch multiplier: 1 (avoid task hoarding)
- Max tasks per child: 1000 (prevent memory leaks)

**Critical Tasks**:
- `embed_note_task` - Generate embedding for note (triggered by API or file watcher)
- `ingest_document_task` - Parse and embed uploaded documents
- `cleanup_old_data` - Daily retention cleanup (3am UTC)
- `cleanup_expired_idempotency_keys` - Hourly cleanup
- `schedule_google_calendar_syncs` - Every 15 minutes
- `sync_google_calendar_push` - Per-user push to Google
- `sync_google_calendar_pull` - Per-user pull from Google

**APScheduler Integration** (`app/worker/scheduler.py`):
- Redis jobstore for persistence
- Fires reminders at `due_at_utc`
- Tracks SLO: `reminder_fire_lag_seconds` (target: <30s)

### Security Considerations

**User Isolation**:
- **ALL database queries MUST filter by user_id**
- Qdrant searches use `must` filter: `{"key": "user_id", "match": {"value": str(user_id)}}`
- Never use `@lru_cache` on functions that query by user_id (causes cross-user data leaks)

**Authentication**:
- Session tokens: 30-day expiry, SHA-256 hashed in DB
- Passkeys: WebAuthn credentials with challenge/response
- TOTP: Time-based one-time passwords with hashed backup codes
- Legacy API tokens: Environment variable `API_TOKEN` for backward compatibility

**Idempotency**:
- Prevents duplicate reminders, notes, calendar events
- 24-hour TTL on idempotency keys
- Client provides `Idempotency-Key` header (UUID recommended)

**Encrypted Storage**:
- Google Calendar OAuth tokens encrypted with Fernet (`GOOGLE_TOKEN_ENCRYPTION_KEY`)
- Passwords hashed with bcrypt (cost factor 12)
- Session tokens hashed with SHA-256 before storage

### RAG (Retrieval Augmented Generation)

**Service**: `app/api/services/rag_service.py`

**Flow**:
1. User message received at `/api/v1/chat`
2. Generate embedding for query
3. Vector search in Qdrant (top 5 results, min_score=0.5)
4. Format context from search results
5. LLM adapter generates response with context
6. Return answer + citations

**LLM Adapters** (`app/api/adapters/llm_adapter.py`):
- `dummy`: Returns placeholder (no API key needed)
- `ollama`: Local/remote Ollama with streaming
- `openai`: OpenAI Chat Completions API
- `anthropic`: Anthropic Messages API with streaming
- `custom`: Any OpenAI-compatible endpoint

**Configuration**: Set `LLM_BACKEND` env var to choose adapter.

### OpenMemory Integration (Long-term AI Memory)

**Purpose**: Provides persistent conversational memory and context across chat sessions.

**Components**:
- **Adapter**: `app/api/adapters/openmemory_adapter.py` - HTTP client for OpenMemory API
- **Service**: `app/api/services/memory_service.py` - Business logic for memory operations
- **Router**: `app/api/routers/memory.py` - REST API endpoints

**Enhanced RAG Flow** (with OpenMemory):
1. User message received at `/api/v1/chat`
2. **Search OpenMemory** for relevant conversation history (parallel with Qdrant search)
3. Search Qdrant for document/note context
4. Combine both contexts in LLM prompt
5. Generate response with comprehensive context
6. **Store conversation turn** in OpenMemory for future reference

**Configuration**:
```bash
OPENMEMORY_URL=http://localhost:8080  # Your OpenMemory server
OPENMEMORY_API_KEY=                   # Optional API key
OPENMEMORY_ENABLED=true               # Enable/disable integration
```

**API Endpoints**:
- `POST /api/v1/memory` - Store explicit memory (facts, preferences)
- `POST /api/v1/memory/search` - Search memories semantically
- `GET /api/v1/memory` - List all user memories (paginated)
- `DELETE /api/v1/memory/{id}` - Delete specific memory
- `GET /api/v1/memory/context/preview` - Debug conversation context retrieval
- `GET /api/v1/memory/health` - Check OpenMemory connectivity

**Memory Sectors** (automatically determined by OpenMemory):
- `semantic`: Facts and conceptual knowledge
- `episodic`: Specific events and experiences
- `procedural`: How-to knowledge and workflows
- `emotional`: Emotional context and sentiment
- `reflective`: Insights and meta-cognition

Each memory is automatically classified into 2-3 relevant sectors with one embedding per sector for multi-dimensional recall. Composite scoring: 60% similarity + 20% salience + 10% recency + 10% link weight.

**User Isolation**: All memories are strictly scoped by `user_id` - one user cannot access another's memories.

**Graceful Degradation**: If OpenMemory is disabled or unavailable, RAG falls back to Qdrant-only search without errors.

**Documentation**: See `docs/OPENMEMORY_INTEGRATION.md` for detailed usage guide and examples.

### Google Calendar Sync

**Service**: `app/api/services/google_calendar_service.py`

**OAuth Flow**:
1. User calls `/api/v1/calendar/google/connect`
2. Redirect to Google consent screen
3. Callback at `/api/v1/calendar/google/callback`
4. Store encrypted OAuth tokens in `google_calendar_tokens` table

**Sync Logic**:
- **One-way (default)**: VIB → Google only
- **Two-way**: Bidirectional sync with conflict resolution
- Debounce window: 5 minutes (prevent sync storms)
- Background jobs every 15 minutes via Celery beat

**Repository**: `common/google_calendar.py` - Handles credential refresh, API calls, error handling

## Development Best Practices

### Working with Database

**Always use async context managers for transactions**:
```python
async with db.transaction():
    await db.execute("INSERT INTO notes ...")
    # Rollback automatic on exception
```

**Never use @lru_cache on DB functions**:
```python
# ❌ BAD - causes race conditions and cross-user leaks
@lru_cache(maxsize=128)
async def get_user_notes(user_id: UUID):
    ...

# ✅ GOOD - no caching on DB queries
async def get_user_notes(user_id: UUID):
    ...
```

**Always filter by user_id**:
```python
# All queries must include user_id filter
query = "SELECT * FROM notes WHERE user_id = $1 AND id = $2"
result = await db.fetchrow(query, user_id, note_id)
```

### Working with Celery Tasks

**Use absolute paths in worker tasks**:
```python
# ❌ BAD - relative path breaks in worker container
with open("../vault/note.md") as f:
    ...

# ✅ GOOD - absolute path
with open("/vault/notes/note.md") as f:
    ...
```

**Handle async code in Celery tasks**:
```python
@celery_app.task
def my_task():
    # Celery tasks are sync, wrap async code
    asyncio.run(async_function())
```

### Working with Embeddings

**Always use EmbeddingService**:
```python
from api.services.embedding_service import EmbeddingService

service = EmbeddingService()
embedding = await service.create_embedding(text)
# Returns list of 384 floats
```

**Vector search with user isolation**:
```python
from api.services.vector_service import VectorService

service = VectorService()
results = await service.search(
    query_vector=embedding,
    user_id=user_id,  # Critical: isolates results
    limit=5,
    min_score=0.5
)
```

### Middleware Ordering

Middleware executes in **LIFO order** (last added = first to execute):

```python
# 1. Metrics (outermost, measures everything)
app.add_middleware(MetricsMiddleware)

# 2. Idempotency (before auth, needs to cache auth responses)
app.add_middleware(IdempotencyMiddleware)

# 3. CORS (innermost)
app.add_middleware(CORSMiddleware)
```

Auth is a dependency, not middleware, so it runs after CORS.

### Hot Reload During Development

**Code changes that require rebuild**:
- Dependencies in `requirements.txt`
- Dockerfile or entrypoint.sh
- Environment variables in `.env`

**Code changes with hot reload** (no rebuild needed):
- Python files in `app/api/` (orchestrator auto-reloads)
- Python files in `app/worker/` (restart worker: `docker compose restart worker`)
- SQL migrations (run manually)

**Smart rebuild** (preserves Docker layer cache):
```bash
# Only rebuild if requirements changed
docker compose up -d --build orchestrator
```

### Testing Philosophy

Tests are **integration tests**, not unit tests:
- Each stage tests end-to-end functionality
- Tests use real Docker containers (postgres, redis, qdrant)
- Test data is cleaned up after each run
- Tests use assertions with detailed error messages

**Test utilities** (`tests/common.sh`):
- `assert_equals`, `assert_contains`, `assert_greater_than`
- `wait_for` - polls condition with timeout
- `psql_query` - executes PostgreSQL query
- `ensure_note_fixture` - creates test data

## File Watcher Troubleshooting

**Windows/Docker Issue**: The file watcher MUST use `PollingObserver`, not `Observer`. Native inotify events don't propagate from Windows host to Docker containers.

**Location**: `app/worker/tasks.py:608-618`

**If file watcher not working**:
1. Check worker logs: `docker compose logs worker | grep file_watcher`
2. Verify PollingObserver is used (not Observer)
3. Check debounce timing (5 seconds)
4. Verify `/vault` volume is mounted in worker container
5. Test with: `echo "test" >> vault/notes/test.md` and check `file_sync_state.last_embedded_at`

## Common Pitfalls

1. **Forgetting user_id filter**: Always filter queries by user_id
2. **Using @lru_cache on DB functions**: Causes race conditions
3. **Relative paths in worker tasks**: Use absolute paths like `/vault/...`
4. **Not using transactions**: Wrap multi-step DB operations in `async with db.transaction()`
5. **Middleware ordering**: Remember LIFO execution order
6. **File watcher on Windows**: Must use PollingObserver
7. **Idempotency keys**: Don't forget to pass `Idempotency-Key` header for POST/PUT/PATCH
8. **Google Calendar tokens**: Must be encrypted with Fernet, not stored as plaintext
