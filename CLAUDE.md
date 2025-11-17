# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Brainda is a personal knowledge management system combining note-taking, document ingestion, semantic search, RAG chat, smart reminders, and calendar scheduling. It's a microservices architecture running on Docker Compose with 8 development stages (Stage 0-8) testing progressive features.

## Architecture

### Service Components

The application uses **container-based service selection** via `entrypoint.sh`:
- If `SERVICE=worker`: Runs Celery worker (`celery -A worker.tasks worker`)
- If `SERVICE=beat`: Runs Celery beat scheduler (`celery -A worker.tasks beat`)
- Otherwise: Runs FastAPI orchestrator (`uvicorn api.main:app`)

**Docker Services (varies by configuration mode):**

**Base Services** (all modes):
1. **orchestrator** (brainda-orchestrator): FastAPI API server on port 8000
2. **worker** (brainda-worker): Celery background task processor
3. **beat** (brainda-beat): Celery beat scheduler for periodic tasks
4. **postgres** (brainda-postgres): PostgreSQL 15 database on port 5434
5. **redis** (brainda-redis): Redis 7 message broker/cache on port 6379
6. **qdrant** (brainda-qdrant): Vector database on port 6333

**Additional in Development Mode** (`docker-compose.dev.yml`):
7. **frontend** (brainda-frontend): Vite dev server on port 3000 with hot reload

**Production Mode** (`docker-compose.prod.yml`):
- Uses `Dockerfile.prod` multi-stage build
- Frontend built and served from orchestrator (no separate frontend service)
- Single endpoint: http://localhost:8000

### Docker Configuration Files

**Dockerfiles:**
- `Dockerfile`: Original backend-only Dockerfile (legacy)
- `Dockerfile.dev`: Development Dockerfile (code mounted as volumes, no copy)
- `Dockerfile.prod`: Production multi-stage build (Node.js → Python, includes built frontend)

**Docker Compose Files:**
- `docker-compose.yml`: Base configuration (backend services only)
- `docker-compose.dev.yml`: Development overlay (adds frontend service, enables hot reload)
- `docker-compose.prod.yml`: Production configuration (uses Dockerfile.prod, optimized builds)

**See [DOCKER_SETUP.md](./DOCKER_SETUP.md) for comprehensive Docker configuration guide.**

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

### Docker Configuration Modes

Brainda supports three Docker configuration modes. **See [DOCKER_SETUP.md](./DOCKER_SETUP.md) for comprehensive documentation.**

#### Development Mode (Recommended for Active Development)

**Best for**: Daily development with hot reload for frontend + backend

```bash
# Start all services including frontend with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# View logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f orchestrator frontend

# Stop all services
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

**Access:**
- Frontend: http://localhost:3000 (Vite dev server with hot reload)
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

**Features:**
- ✅ Frontend hot reload (Vite dev server)
- ✅ Backend hot reload (FastAPI `--reload`)
- ✅ No rebuilds needed for code changes
- ✅ Separate frontend container (`brainda-frontend`)
- ✅ All code mounted as volumes

#### Production Mode (Recommended for Deployment)

**Best for**: Production deployment, testing production builds

```bash
# Build and start all services (frontend built and served from FastAPI)
docker compose -f docker-compose.prod.yml up -d --build

# View logs
docker compose -f docker-compose.prod.yml logs -f orchestrator

# Stop all services
docker compose -f docker-compose.prod.yml down
```

**Access:**
- Everything: http://localhost:8000 (frontend + backend on single port)

**Features:**
- ✅ Multi-stage Docker build (Node.js → Python)
- ✅ Frontend built and optimized (Vite production build)
- ✅ Served from FastAPI static files
- ✅ Single endpoint for frontend + backend
- ✅ Smaller image size
- ✅ Production-optimized

#### Legacy Mode (Not Recommended)

**Best for**: Only if you need to run frontend outside Docker

```bash
# Start backend services only
docker compose up -d

# Manually run frontend (separate terminal)
cd app/web
npm install
npm run dev
```

**Why not recommended**: Requires manual process management, no container benefits for frontend

### Building and Running (General Commands)

```bash
# Rebuild specific service after dependency changes
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build orchestrator
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build worker

# View logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f orchestrator
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f worker

# Restart specific service
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart orchestrator
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart frontend
```

### Manual Development Mode (No Docker - Advanced)

**Only use if you need to run services outside Docker for debugging**

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

# Run Frontend (separate terminal)
cd app/web
npm run dev
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
docker exec -it brainda-postgres psql -U vib -d vib

# Run migration manually
docker exec brainda-postgres psql -U vib -d vib -f /app/migrations/006_add_multi_user_auth.sql

# Query examples
docker exec brainda-postgres psql -U vib -d vib -c "SELECT COUNT(*) FROM notes;"
docker exec brainda-postgres psql -U vib -d vib -c "SELECT * FROM file_sync_state LIMIT 5;"
```

### Debugging

```bash
# Check Redis queue depth
docker exec brainda-redis redis-cli LLEN celery

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
- **One-way (default)**: Brainda → Google only
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

**Development Mode** (`docker-compose.dev.yml`) provides the best hot reload experience:

**Code changes with automatic hot reload** (no rebuild, no restart needed):
- **Frontend** files in `app/web/src/` - Vite automatically reloads browser
- **Backend** Python files in `app/api/` - FastAPI orchestrator auto-reloads
- **Styling** files in `app/web/src/` - CSS changes reflect immediately

**Code changes requiring service restart** (no rebuild needed):
- Python files in `app/worker/` → `docker compose -f docker-compose.yml -f docker-compose.dev.yml restart worker`
- Python files in `app/worker/tasks.py` → `docker compose -f docker-compose.yml -f docker-compose.dev.yml restart worker`

**Code changes requiring rebuild**:
- Dependencies in `requirements.txt` or `package.json`
- Dockerfile, Dockerfile.dev, or Dockerfile.prod
- Environment variables in `.env` (restart needed)
- Docker compose files

**Smart rebuild** (preserves Docker layer cache):
```bash
# Development mode - rebuild after dependency changes
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build orchestrator frontend

# Production mode - rebuild frontend + backend
docker compose -f docker-compose.prod.yml up -d --build orchestrator
```

**Development Workflow Best Practices**:
1. **Use development mode** for daily coding: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d`
2. **Code changes** in `app/web/src` or `app/api/` → No action needed (auto-reload)
3. **Worker changes** → `docker compose -f docker-compose.yml -f docker-compose.dev.yml restart worker`
4. **Dependency changes** → Rebuild with `--build` flag
5. **Test production builds** before deploying: `docker compose -f docker-compose.prod.yml up -d --build`

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

## Frontend Architecture

### Tech Stack

**Location**: `app/web/`

**Framework**: React 18 with TypeScript
**Build Tool**: Vite 7
**Routing**: React Router v6
**Styling**: CSS Modules + CSS Variables

### Project Structure

```
app/web/
├── src/
│   ├── components/       # Reusable UI components
│   │   ├── chat/         # Chat-specific components (MessageList, ChatInput, ConversationItem)
│   │   ├── layout/       # Layout components (Header, Sidebar, MobileNav)
│   │   ├── shared/       # Shared components (LoadingSpinner, etc.)
│   │   └── search/       # Search components
│   ├── pages/            # Page-level components (ChatPage, NotesPage, etc.)
│   ├── layouts/          # Layout wrappers (MainLayout)
│   ├── hooks/            # Custom React hooks
│   ├── contexts/         # React contexts
│   └── App.tsx           # Root application component
├── public/               # Static assets
└── package.json          # Frontend dependencies
```

### Key Components

**MainLayout** (`src/layouts/MainLayout.tsx`):
- Root layout wrapper for all authenticated pages
- Manages sidebar collapse/expand state
- Handles mobile/tablet responsive behavior
- Integrates Header, Sidebar, and MobileNav components
- Provides global search functionality (Cmd+K / Ctrl+K)

**Sidebar** (`src/components/layout/Sidebar.tsx`):
- Main navigation sidebar
- **Conditionally shows chat history** when on chat page (`/` or `/chat`)
- Shows standard navigation items on other pages
- Integrates with `useChatConversations` hook for conversation management
- Props:
  - `currentConversationId`: Currently active conversation
  - `onConversationSelect`: Handler for selecting a conversation
  - `onNewConversation`: Handler for starting new chat
- Responsive: Fixed position on mobile/tablet, static on desktop
- Swipe-to-close gesture support on mobile

**ChatPage** (`src/pages/ChatPage.tsx`):
- Main chat interface
- Manages conversation state via `useChat` and `useConversation` hooks
- **Exposes handlers to MainLayout** via `window.__chatPageHandlers` for sidebar integration
- Shows welcome screen with suggested prompts when no messages
- Components: MessageList, ChatInput
- Uses `useCallback` for memoized handlers to prevent infinite re-renders

### State Management Pattern

**Chat History Integration**:
The chat history sidebar integration uses a window-based communication pattern:

1. **ChatPage** exposes handlers via window object:
```typescript
window.__chatPageHandlers = {
  currentConversationId: string | null,
  onConversationSelect: (id: string) => void,
  onNewConversation: () => void,
};
```

2. **MainLayout** retrieves handlers and passes to Sidebar:
```typescript
const chatHandlers = isChatPage ? window.__chatPageHandlers : null;
<Sidebar {...chatHandlers} />
```

3. **Sidebar** conditionally renders chat history when on chat page

**Important**: Use `useCallback` for all handler functions to prevent infinite re-renders in the useEffect dependency array.

### Running Frontend

**Recommended: Docker Development Mode** (Integrated with Backend)

```bash
# Start entire stack including frontend with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# View frontend logs
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f frontend

# Restart frontend after config changes
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart frontend
```

Access at: http://localhost:3000 (Vite dev server with hot reload)

**Alternative: Manual Mode** (Standalone Frontend - Not Recommended)

Only use this if you need to run frontend outside Docker:

```bash
cd app/web

# Install dependencies
npm install

# Start dev server (with hot reload)
npm run dev
# Opens on http://localhost:3000 (or next available port)

# Note: Backend must be running at http://localhost:8000
# Start backend separately: docker compose up -d
```

**Production Build** (For Testing or Deployment)

```bash
# Build frontend and serve from FastAPI (production mode)
docker compose -f docker-compose.prod.yml up -d --build

# Access everything at http://localhost:8000
```

**Frontend Development Tasks**

```bash
# Type check
cd app/web
npm run type-check

# Build for production (manual)
npm run build

# Run tests
npm test
npm run test:coverage
```

### Development Best Practices

**Component Communication**:
- ✅ **GOOD**: Use window object for cross-component communication (ChatPage ↔ Sidebar)
- ✅ **GOOD**: Wrap handlers in `useCallback` with proper dependencies
- ❌ **BAD**: Creating new function instances on every render
- ❌ **BAD**: Passing unstable references to useEffect dependencies

**Responsive Design**:
- Mobile-first approach with CSS custom properties
- Breakpoints: Mobile (<768px), Tablet (768-1023px), Desktop (≥1024px)
- Use `useIsMobileOrTablet` hook for conditional behavior
- Sidebar is fixed/overlay on mobile/tablet, static on desktop

**Styling**:
- Use CSS Modules for component-scoped styles
- CSS variables defined in root for theming
- Dark mode support via CSS variables
- Follow existing naming convention: `.component__element--modifier`

### Custom Hooks

**useChatConversations** (`src/hooks/useChatConversations.ts`):
- Fetches and manages chat conversation list
- Provides `deleteConversation` mutation
- Returns: `{ conversations, isLoading, error, deleteConversation }`

**useChat** (`src/hooks/useChat.ts`):
- Manages chat messages and streaming
- Handles conversation creation
- Returns: `{ messages, isLoading, sendMessage, clearMessages, loadMessages }`

**useConversation** (`src/hooks/useConversation.ts`):
- Loads messages for a specific conversation ID
- Returns: `{ messages, isLoading }`

## Common Pitfalls

### Backend Pitfalls

1. **Forgetting user_id filter**: Always filter queries by user_id
2. **Using @lru_cache on DB functions**: Causes race conditions
3. **Relative paths in worker tasks**: Use absolute paths like `/vault/...`
4. **Not using transactions**: Wrap multi-step DB operations in `async with db.transaction()`
5. **Middleware ordering**: Remember LIFO execution order
6. **File watcher on Windows**: Must use PollingObserver
7. **Idempotency keys**: Don't forget to pass `Idempotency-Key` header for POST/PUT/PATCH
8. **Google Calendar tokens**: Must be encrypted with Fernet, not stored as plaintext

### Frontend Pitfalls

1. **Infinite re-renders**: Not using `useCallback` for handler functions passed to useEffect dependencies
2. **Stale closures**: Forgetting dependencies in useCallback/useEffect/useMemo hooks
3. **Cross-component state**: Using window object requires cleanup in useEffect return
4. **CSS Modules**: Importing styles as `import styles from './Component.module.css'`, not regular CSS
5. **Path aliases**: Use `@components`, `@hooks`, `@pages` instead of relative paths like `../../../`
6. **Type safety**: Always provide proper TypeScript types for props and state
7. **Mobile testing**: Test responsive behavior on mobile/tablet, not just desktop
