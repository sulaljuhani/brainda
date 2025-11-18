# Brainda - Technical Features Documentation

**Version:** 1.0.0
**Last Updated:** 2025-11-18
**Architecture:** Microservices (Docker Compose)

---

## Table of Contents

1. [Core Features](#core-features)
2. [Knowledge Management](#knowledge-management)
3. [AI & Machine Learning](#ai--machine-learning)
4. [Authentication & Security](#authentication--security)
5. [Data Processing](#data-processing)
6. [API & Integration](#api--integration)
7. [Infrastructure & Deployment](#infrastructure--deployment)
8. [Observability & Monitoring](#observability--monitoring)

---

## Core Features

### 1. Notes Management
**Module:** `app/api/routers/notes.py` (if exists), Vault system

**Technical Capabilities:**
- **Markdown-based storage** in `/vault` directory
- **YAML frontmatter** for metadata (id, title, tags, created_at)
- **File watcher** with PollingObserver (cross-platform compatibility)
  - 5-second debounce for change detection
  - SHA-256 content hashing for change verification
  - Automatic re-embedding on content changes
- **Vector embedding** of note content (title + body)
- **Tag management** for categorization
- **Full-text search** via vector similarity

**Database Schema:**
```sql
notes (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  title TEXT NOT NULL,
  body TEXT,
  tags TEXT[],
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  UNIQUE(user_id, title)
)
```

**Sync State Tracking:**
```sql
file_sync_state (
  user_id UUID,
  file_path TEXT,
  content_hash TEXT,
  last_modified_at TIMESTAMP,
  last_embedded_at TIMESTAMP,
  embedding_model TEXT,
  vector_id TEXT,
  UNIQUE(user_id, file_path)
)
```

---

### 2. Document Ingestion & Processing
**Module:** `app/api/routers/documents.py`, `app/api/services/document_service.py`

**Technical Capabilities:**
- **Multi-format support:**
  - PDF (via `pypdf`)
  - Text files (TXT, MD, CSV)
  - Microsoft Office (DOCX, XLSX, PPTX via `python-docx`, `openpyxl`, `python-pptx`)
  - HTML parsing
  - OCR for images (via `pytesseract`)
- **SHA-256 deduplication** - prevents duplicate uploads
- **Chunking strategy:**
  - Recursive text splitting
  - Configurable chunk size (default: 1000 tokens)
  - Overlap for context preservation
- **Asynchronous processing** via Celery background tasks
- **Job status tracking** (pending → processing → indexed/failed)
- **Metadata extraction:**
  - File size, MIME type, page numbers
  - Creation/modification timestamps
  - Content hash

**Database Schema:**
```sql
documents (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  filename TEXT,
  source TEXT, -- 'upload', 'api', 'sync'
  storage_path TEXT,
  mime_type TEXT,
  sha256 TEXT UNIQUE,
  size_bytes BIGINT,
  status TEXT, -- 'pending', 'processing', 'indexed', 'failed'
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)

chunks (
  id UUID PRIMARY KEY,
  document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
  ordinal INTEGER,
  text TEXT,
  tokens INTEGER,
  metadata JSONB,
  created_at TIMESTAMP
)
```

---

### 3. Reminders System
**Module:** `app/api/routers/reminders.py`, `app/api/services/reminder_service.py`, `app/worker/scheduler.py`

**Technical Capabilities:**
- **Timezone-aware scheduling**
  - Stores both `due_at_utc` and `due_at_local`
  - User-configurable timezone
- **Recurrence patterns** (RFC 5545 RRULE)
  - Daily, weekly, monthly, yearly
  - Custom intervals and end dates
  - BYDAY, BYMONTH, BYMONTHDAY support
- **APScheduler integration**
  - Redis-backed job store for persistence
  - Automatic reminder firing at due time
  - SLO tracking: <30s fire lag
- **Status lifecycle:**
  - active → dismissed/completed
  - Snooze functionality (add minutes to due time)
- **Idempotency protection**
  - Content-based deduplication
  - `Idempotency-Key` header support (24h TTL)
- **Category management** for organization
- **Calendar event linking**
- **Task linking** for project management

**Database Schema:**
```sql
reminders (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  title TEXT NOT NULL,
  body TEXT,
  due_at_utc TIMESTAMP NOT NULL,
  due_at_local TIMESTAMP,
  timezone TEXT,
  repeat_rrule TEXT, -- RFC 5545 format
  status TEXT, -- 'active', 'dismissed', 'completed', 'snoozed'
  calendar_event_id UUID,
  category_id UUID,
  task_id UUID,
  offset_days INTEGER,
  offset_type TEXT,
  idempotency_key_ref TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

**Scheduler Architecture:**
- **APScheduler** with Redis job store
- **Cron-based triggers** for recurring reminders
- **Graceful shutdown** with job persistence
- **Automatic sync** of database reminders on startup

---

### 4. Calendar Events Management
**Module:** `app/api/routers/calendar.py`, `app/api/services/calendar_service.py`

**Technical Capabilities:**
- **Event creation** with start/end times
- **Timezone support** (per-event)
- **Recurrence rules** (RFC 5545 RRULE)
  - Validation: max 1000 instances in 2 years
  - Runtime expansion for list queries
- **RRULE expansion** on-the-fly for queries
- **Status management:**
  - confirmed, tentative, cancelled
- **Category assignment** for organization
- **Reminder linking** (bi-directional)
- **Location text field**
- **Google Calendar sync** (see Integration section)

**Database Schema:**
```sql
calendar_events (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  starts_at TIMESTAMP NOT NULL,
  ends_at TIMESTAMP,
  timezone TEXT,
  location_text TEXT,
  rrule TEXT, -- RFC 5545 format
  status TEXT, -- 'confirmed', 'tentative', 'cancelled'
  source TEXT, -- 'local', 'google'
  category_id UUID,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)
```

**RRULE Expansion:**
- Uses `python-dateutil` for parsing
- Limits: 1000 instances per query to prevent DoS
- Caches expansion results per request

---

### 5. Tasks Management
**Module:** `app/api/routers/tasks.py`, `app/api/services/task_service.py`

**Technical Capabilities:**
- **Task lifecycle:**
  - todo → in_progress → completed/cancelled
- **Priority levels** (low, medium, high)
- **Due dates** with timezone support
- **Category assignment**
- **Reminder integration** (offset-based)
- **Subtask support** (parent-child relationships)
- **Dependency tracking** (blocks/blocked_by)

**Database Schema:**
```sql
tasks (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT, -- 'todo', 'in_progress', 'completed', 'cancelled'
  priority TEXT, -- 'low', 'medium', 'high'
  due_at TIMESTAMP,
  category_id UUID,
  parent_task_id UUID,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  completed_at TIMESTAMP
)
```

---

### 6. Chat Interface & RAG
**Module:** `app/api/routers/chat.py`, `app/api/services/rag_service.py`

**Technical Capabilities:**
- **Conversation management:**
  - Multi-conversation support per user
  - Conversation title auto-generation
  - Message history persistence
  - Conversation deletion
- **RAG (Retrieval Augmented Generation):**
  - Vector search in Qdrant (top 5 results, min_score=0.5)
  - OpenMemory integration for long-term context
  - Citation tracking with source references
  - Context window management
- **File attachments:**
  - Images (JPG, PNG, GIF, WebP) with thumbnail generation
  - Documents (PDF, DOCX, TXT)
  - Audio (MP3, WAV, M4A) with Whisper transcription
  - Video (MP4, MOV, AVI) metadata extraction
  - File size limits: 10MB per file, 50MB per message
  - Rate limiting: 20 files/minute per user
- **Streaming responses** for real-time output
- **Tool calling support:**
  - Calendar management (create, update, delete events)
  - Reminder management (create, update, snooze)
  - Task management (create, update, complete)
  - Search knowledge base
- **Model selection:**
  - Dynamic model switching per conversation
  - Support for OpenAI, Anthropic, Ollama, custom endpoints

**Database Schema:**
```sql
chat_conversations (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  title TEXT DEFAULT 'New Chat',
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)

chat_messages (
  id UUID PRIMARY KEY,
  conversation_id UUID REFERENCES chat_conversations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  role TEXT, -- 'user', 'assistant'
  content TEXT,
  tool_calls JSONB,
  citations JSONB,
  attachments JSONB,
  created_at TIMESTAMP
)

chat_files (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  conversation_id UUID,
  message_id UUID,
  original_filename TEXT,
  storage_path TEXT,
  mime_type TEXT,
  file_size_bytes BIGINT,
  status TEXT, -- 'pending', 'processing', 'ready', 'failed'
  metadata JSONB,
  created_at TIMESTAMP
)
```

---

## Knowledge Management

### 7. Vector Search & Semantic Retrieval
**Module:** `app/api/services/vector_service.py`, `app/api/routers/search.py`

**Technical Capabilities:**
- **Embedding model:** `sentence-transformers/all-MiniLM-L6-v2`
  - Dimensions: 384
  - Distance metric: Cosine similarity
- **Vector database:** Qdrant
  - Collection: `knowledge_base`
  - User isolation via payload filters
- **Content types:**
  - `note` - Notes from vault
  - `document_chunk` - Document chunks
- **Hybrid search:**
  - Vector similarity search
  - Keyword matching (ILIKE) for filenames/chunks
  - Result deduplication and merging
- **Query parameters:**
  - `min_score` - Similarity threshold (default: 0.1)
  - `limit` - Max results (1-50)
  - `content_type` - Filter by type
- **Metadata storage:**
  - User ID (for isolation)
  - Content type, title, body
  - Timestamps (created_at, embedded_at)
  - Embedding model version

**Qdrant Payload Structure:**
```json
{
  "embedding_model": "all-MiniLM-L6-v2",
  "content_type": "note|document_chunk",
  "source_id": "uuid",
  "title": "...",
  "user_id": "uuid",
  "chunk_index": 0,
  "parent_document_id": "uuid",
  "text": "...",
  "tokens": 500,
  "page": 5,
  "created_at": "2025-11-18T00:00:00Z",
  "embedded_at": "2025-11-18T00:00:00Z"
}
```

---

### 8. Categories System
**Module:** `app/api/routers/categories.py`, `app/api/services/category_service.py`

**Technical Capabilities:**
- **Hierarchical categories** (name, color, icon)
- **Category types:**
  - `reminder_categories` - For reminders
  - `event_categories` - For calendar events
  - `task_categories` - For tasks
- **Color coding** (hex values)
- **Icon assignment** (Lucide icon names)
- **Usage tracking:**
  - Count of items per category
  - Last used timestamp

**Database Schema:**
```sql
reminder_categories (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  name TEXT NOT NULL,
  color TEXT,
  icon TEXT,
  created_at TIMESTAMP,
  UNIQUE(user_id, name)
)

event_categories (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  name TEXT NOT NULL,
  color TEXT,
  icon TEXT,
  created_at TIMESTAMP,
  UNIQUE(user_id, name)
)
```

---

## AI & Machine Learning

### 9. LLM Provider Abstraction
**Module:** `app/api/adapters/llm_adapter.py`

**Technical Capabilities:**
- **Provider support:**
  - **OpenAI** - Chat Completions API
  - **Anthropic** - Messages API (Claude)
  - **Ollama** - Local/remote deployment
  - **Custom** - Any OpenAI-compatible endpoint
  - **Dummy** - Placeholder for development
- **Features:**
  - Streaming support (all providers)
  - Tool calling (OpenAI, Anthropic native)
  - Token counting (tiktoken)
  - Retry logic (exponential backoff, 3 attempts)
  - Circuit breaker pattern (prevents runaway costs)
  - Timeout configuration (60s for LLM, 30s for HTTP)
- **Dynamic model selection:**
  - User-configurable models per conversation
  - Database-stored model configurations
  - Per-model API keys and settings

**Circuit Breaker:**
```python
CIRCUIT_BREAKER_MAX_FAILURES=5
CIRCUIT_BREAKER_RESET_TIMEOUT=60  # seconds
```

**Supported Models (examples):**
- OpenAI: gpt-4, gpt-3.5-turbo
- Anthropic: claude-3-5-sonnet-20241022, claude-3-opus
- Ollama: llama3, mistral, codellama
- Custom: Any compatible API

---

### 10. Embedding Service
**Module:** `app/api/services/embedding_service.py`, `common/embeddings.py`

**Technical Capabilities:**
- **Model:** `sentence-transformers/all-MiniLM-L6-v2`
  - Pre-downloaded during Docker build
  - Cached singleton per worker process
- **Batch processing** (batch_size=16)
- **Async execution:**
  - Uses `run_in_executor` for CPU-bound operations
  - Non-blocking embedding generation
- **Fallback:** Mock embeddings for testing (deterministic, SHA-256 based)
- **Metrics tracking:**
  - `embedding_duration_seconds` histogram
  - Labels: `source_type` (note, document)

**Performance:**
- Typical embedding time: 50-200ms per text
- Batch processing: ~5-10x speedup for multiple texts
- Vector dimension: 384 floats

---

### 11. OpenMemory Integration (Long-term AI Memory)
**Module:** `app/api/adapters/openmemory_adapter.py`, `app/api/services/memory_service.py`

**Technical Capabilities:**
- **Memory sectors** (auto-classified):
  - `semantic` - Facts and conceptual knowledge
  - `episodic` - Specific events and experiences
  - `procedural` - How-to knowledge and workflows
  - `emotional` - Emotional context and sentiment
  - `reflective` - Insights and meta-cognition
- **Features:**
  - Semantic search across memories
  - Automatic sector classification (2-3 sectors per memory)
  - Composite scoring: 60% similarity + 20% salience + 10% recency + 10% link weight
  - User isolation (strict scoping)
  - Graceful degradation (falls back to Qdrant-only)
- **RAG enhancement:**
  - Combines OpenMemory context with Qdrant document search
  - Provides conversation history for better responses
  - Stores successful interactions for future reference
- **Memory Vault sync** (optional):
  - Mirrors memories to markdown files
  - File format: `YYYY-MM-DD-HHMMSS-uuid.md`
  - YAML frontmatter with metadata

**Configuration:**
```bash
OPENMEMORY_URL=http://localhost:8080
OPENMEMORY_ENABLED=true
MEMORY_VAULT_SYNC_ENABLED=false
MEMORY_VAULT_PATH=/memory_vault
```

---

### 12. Audio Transcription (Whisper)
**Module:** `app/worker/tasks.py` (Whisper integration), `app/api/routers/transcribe.py`

**Technical Capabilities:**
- **Model:** OpenAI Whisper
  - Model sizes: tiny, base, small, medium, large
  - Default: `base` (good balance of speed/accuracy)
  - Device support: CPU, CUDA (GPU)
- **Audio format support:**
  - MP3, WAV, M4A, FLAC, OGG
  - Automatic format conversion via ffmpeg
- **Features:**
  - Language detection (auto)
  - Timestamped segments
  - Speaker diarization (basic)
- **Singleton model loading:**
  - Thread-safe model caching per worker
  - Model cached in `/app/.cache/whisper`
- **Integration:**
  - Chat file attachments
  - Standalone transcription endpoint

**Configuration:**
```bash
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_MODEL_CACHE=/app/.cache/whisper
```

---

## Authentication & Security

### 13. Multi-User Authentication
**Module:** `app/api/routers/auth.py`, `app/api/services/auth_service.py`

**Technical Capabilities:**
- **Registration:**
  - Username validation (min 3 chars, alphanumeric + hyphens/underscores)
  - Password validation (min 8 chars)
  - Email validation (optional, unique)
  - Bcrypt password hashing (cost factor: 12)
  - Duplicate prevention (username, email)
- **Login:**
  - Username + password authentication
  - Session token generation (48-byte URL-safe)
  - Session expiry (30 days)
  - SHA-256 token hashing in database
- **Session management:**
  - Multiple concurrent sessions per user
  - Session touch (updates `last_active_at`)
  - Session invalidation on logout
  - Automatic session cleanup (expired sessions)
- **Profile management:**
  - Update display name, email, avatar
  - Email uniqueness validation
- **Password management:**
  - Change password (requires current password)
  - Invalidates all other sessions on change
- **Audit logging:**
  - All auth events logged (login, logout, registration, failures)
  - IP address and user agent tracking

**Database Schema:**
```sql
users (
  id UUID PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  email TEXT UNIQUE,
  display_name TEXT,
  avatar_url TEXT,
  api_token TEXT, -- legacy
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)

sessions (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT UNIQUE NOT NULL,
  device_type TEXT,
  ip_address TEXT,
  user_agent TEXT,
  created_at TIMESTAMP,
  expires_at TIMESTAMP,
  last_active_at TIMESTAMP
)

auth_events (
  id UUID PRIMARY KEY,
  user_id UUID,
  event_type TEXT, -- 'login_success', 'login_failed', 'logout', etc.
  ip_address TEXT,
  user_agent TEXT,
  metadata JSONB,
  created_at TIMESTAMP
)
```

---

### 14. Passkey (WebAuthn) Support
**Module:** `app/api/routers/devices.py`

**Technical Capabilities:**
- **WebAuthn authentication:**
  - FIDO2 passkey registration
  - Challenge-response authentication
  - Public key cryptography
- **Device management:**
  - Multiple passkeys per user
  - Device naming and identification
  - Last used tracking
  - Device revocation
- **Features:**
  - Passwordless authentication
  - Biometric support (fingerprint, Face ID)
  - Hardware security key support (YubiKey, etc.)
  - Phishing-resistant authentication

**Database Schema:**
```sql
passkey_credentials (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  credential_id TEXT UNIQUE NOT NULL,
  public_key TEXT NOT NULL,
  device_name TEXT,
  device_type TEXT,
  aaguid TEXT,
  counter INTEGER DEFAULT 0,
  created_at TIMESTAMP,
  last_used_at TIMESTAMP
)
```

---

### 15. TOTP (Time-based One-Time Password)
**Module:** `app/api/routers/totp.py`

**Technical Capabilities:**
- **TOTP setup:**
  - Secret key generation (32 bytes)
  - QR code generation for authenticator apps
  - Verification before enabling
- **Backup codes:**
  - 8 backup codes generated on setup
  - Bcrypt hashing (cost factor: 12)
  - Single-use validation
- **TOTP validation:**
  - 30-second time window
  - Tolerance: ±1 window (handles clock drift)
  - Rate limiting (prevents brute force)
- **Compatible apps:**
  - Google Authenticator
  - Authy
  - Microsoft Authenticator
  - 1Password, etc.

**Database Schema:**
```sql
totp_secrets (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
  secret_key TEXT NOT NULL,
  enabled BOOLEAN DEFAULT FALSE,
  backup_codes_hash TEXT[],
  created_at TIMESTAMP
)
```

---

### 16. Security Features

**User Isolation:**
- **Database level:** All queries filter by `user_id`
- **Vector DB level:** Qdrant payload filters on `user_id`
- **File system level:** User-specific folders (`/uploads/{user_id}/`)
- **Session level:** Token-to-user_id mapping

**SQL Injection Prevention:**
- **Parameterized queries:** All queries use `$1`, `$2` placeholders
- **Whitelist validation:** Status filters use predefined sets
- **Safe f-strings:** Only 1 usage, protected by whitelist (tasks.py:188)

**Rate Limiting:**
- **Chat API:** 30 requests/minute per user
- **File uploads:** 20 files/minute per user
- **Sliding window algorithm:** In-memory with asyncio locks

**Encryption:**
- **Google Calendar tokens:** Fernet symmetric encryption
- **Passwords:** Bcrypt with cost factor 12
- **Session tokens:** SHA-256 hashing before storage
- **TOTP backup codes:** Bcrypt hashing

**Content Security:**
- **File type validation:** MIME type + magic number checking
- **File size limits:** 10MB per file, 50MB per message
- **Path traversal prevention:** No user-controlled file paths
- **XSS prevention:** Frontend sanitizes all user input

**CORS Configuration:**
- **Whitelist origins:** Never use `*` with credentials
- **Credentials support:** Cookies, Authorization headers
- **Preflight handling:** OPTIONS requests

**Docker Security:**
- **Non-root user:** Containers run as `brainda:1000`
- **ONNX Runtime verification:** No executable stack
- **No seccomp:unconfined:** Default Docker seccomp profile
- **Init system:** Prevents zombie processes

---

## Data Processing

### 17. Background Job Processing (Celery)
**Module:** `app/worker/tasks.py`

**Technical Capabilities:**
- **Worker configuration:**
  - Concurrency: 3 workers (configurable)
  - Prefetch multiplier: 1 (prevents task hoarding)
  - Max tasks per child: 1000 (prevents memory leaks)
  - Time limits: 900s hard, 840s soft
- **Task types:**
  - `health_check` - Worker health verification
  - `embed_note_task` - Note embedding
  - `schedule_embedding_check` - Debounced embedding check
  - `process_document_ingestion` - Document parsing and chunking
  - `cleanup_old_data` - Data retention (daily at 3am UTC)
  - `cleanup_expired_idempotency_keys` - Hourly cleanup
  - `cleanup_orphaned_chat_files` - Hourly cleanup
  - `schedule_google_calendar_syncs` - Every 15 minutes
  - `sync_google_calendar_push` - Push events to Google
  - `sync_google_calendar_pull` - Pull events from Google
  - `process_chat_file_task` - Process chat attachments
- **Retry logic:**
  - Exponential backoff (1s, 2s, 4s, 8s)
  - Max retries: 3
  - Automatic task requeueing on failure
- **Metrics:**
  - `celery_queue_depth` - Tasks in queue
  - `documents_ingested_total` - Successful ingestions
  - `documents_failed_total` - Failed ingestions
  - `document_ingestion_duration_seconds` - Processing time

**Celery Beat Schedule:**
```python
{
  "cleanup-old-data": crontab(hour=3, minute=0),  # Daily 3am UTC
  "cleanup-idempotency-keys": crontab(minute=0),  # Hourly
  "cleanup-orphaned-files": crontab(minute=0),    # Hourly
  "google-calendar-sync": crontab(minute="*/15"), # Every 15min
}
```

---

### 18. Data Retention & Cleanup
**Module:** `app/worker/tasks.py` (cleanup tasks)

**Technical Capabilities:**
- **Configurable retention periods:**
  - Messages: 90 days (default)
  - Jobs: 30 days (default)
  - Notifications: 60 days (default)
  - Audit logs: 365 days (default)
- **Cleanup operations:**
  - Soft deletes (updates status to 'deleted')
  - Hard deletes (removes from database)
  - Vacuum analyze (reclaims space)
- **Orphaned resource cleanup:**
  - Chat files without messages
  - Documents without chunks
  - Vector embeddings without sources
- **Metrics:**
  - `retention_cleanup_total` - Items cleaned per type
  - `retention_cleanup_duration_seconds` - Cleanup time

**Configuration:**
```bash
RETENTION_MESSAGES=90
RETENTION_JOBS=30
RETENTION_NOTIFICATIONS=60
RETENTION_AUDIT_LOG=365
```

---

### 19. File Watcher System
**Module:** `app/worker/tasks.py:567-618`

**Technical Capabilities:**
- **Observer type:** `PollingObserver`
  - Reason: Cross-platform compatibility (Windows Docker)
  - Poll interval: 1 second
  - Recursive monitoring of `/vault`
- **Debounce strategy:**
  - 5-second debounce after file modification
  - Prevents duplicate embedding tasks
  - Dictionary-based last-processed tracking
- **Change detection:**
  - SHA-256 content hashing
  - Compares against `file_sync_state.content_hash`
  - Only re-embeds if content actually changed
- **Note ID extraction:**
  - Parses YAML frontmatter
  - Extracts `id` field
  - Links file to database note record
- **Error handling:**
  - Graceful failure on parse errors
  - Logs errors without stopping watcher
  - Continues monitoring other files

**Important Note:** Must use `PollingObserver`, not `Observer` on Windows/Docker.

---

## API & Integration

### 20. Google Calendar Sync
**Module:** `app/api/routers/google_calendar.py`, `common/google_calendar.py`

**Technical Capabilities:**
- **OAuth 2.0 flow:**
  - Authorization code grant
  - PKCE state token (CSRF protection)
  - Refresh token storage (encrypted)
  - Automatic token refresh
- **Sync directions:**
  - **One-way:** Brainda → Google (default)
  - **Two-way:** Bidirectional sync with conflict resolution
- **Sync features:**
  - Event creation, update, deletion
  - Recurrence rule mapping (RRULE)
  - Timezone conversion
  - Conflict detection (last-modified-wins)
- **Debounce:** 5-minute window to prevent sync storms
- **Scheduled sync:** Every 15 minutes via Celery beat
- **Manual sync:** On-demand via API endpoint
- **Error handling:**
  - Token expiration (auto-refresh)
  - Network failures (retry with backoff)
  - Invalid events (logged, skipped)

**Database Schema:**
```sql
google_calendar_tokens (
  id UUID PRIMARY KEY,
  user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  encrypted_token TEXT NOT NULL,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)

google_calendar_sync_state (
  id UUID PRIMARY KEY,
  user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  sync_enabled BOOLEAN DEFAULT TRUE,
  sync_direction TEXT, -- 'one_way', 'two_way'
  sync_token TEXT,
  google_calendar_id TEXT,
  last_sync_at TIMESTAMP,
  created_at TIMESTAMP
)
```

**Configuration:**
```bash
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/calendar/google/callback
GOOGLE_TOKEN_ENCRYPTION_KEY=fernet-key
GOOGLE_SYNC_DEBOUNCE_SECONDS=300
```

---

### 21. RESTful API
**Module:** `app/api/main.py`, All routers

**Technical Capabilities:**
- **API versioning:** `/api/v1/`
- **Authentication:** Bearer token (session or API token)
- **Content negotiation:** JSON (request/response)
- **HTTP methods:**
  - GET - Read operations
  - POST - Create operations
  - PATCH - Partial update operations
  - DELETE - Delete operations
- **Standard response format:**
  ```json
  {
    "success": true|false,
    "data": {...},
    "error": {
      "code": "ERROR_CODE",
      "message": "Human-readable message"
    }
  }
  ```
- **Error codes:**
  - 400 - Bad Request (validation errors)
  - 401 - Unauthorized (missing/invalid token)
  - 404 - Not Found
  - 413 - Payload Too Large (file size)
  - 429 - Too Many Requests (rate limit)
  - 500 - Internal Server Error
- **Pagination:**
  - Cursor-based (for documents)
  - Offset + limit (for conversations)
- **OpenAPI documentation:**
  - Interactive docs at `/docs` (Swagger UI)
  - JSON schema at `/openapi.json`

**Available Routers:**
- `/api/v1/auth` - Authentication
- `/api/v1/chat` - Chat conversations
- `/api/v1/reminders` - Reminders
- `/api/v1/calendar` - Calendar events
- `/api/v1/calendar/google` - Google Calendar sync
- `/api/v1/ingest` - Document upload
- `/api/v1/documents` - Document management
- `/api/v1/search` - Knowledge base search
- `/api/v1/memory` - OpenMemory integration
- `/api/v1/tasks` - Task management
- `/api/v1/settings` - User settings
- `/api/v1/categories` - Category management
- `/api/v1/devices` - Passkey management
- `/api/v1/totp` - TOTP management
- `/api/v1/models` - LLM model configuration
- `/api/v1/health` - Health check
- `/api/v1/metrics` - Prometheus metrics

---

### 22. Idempotency Middleware
**Module:** `app/api/middleware/idempotency.py`

**Technical Capabilities:**
- **HTTP methods:** POST, PUT, PATCH
- **Header:** `Idempotency-Key` (UUID recommended)
- **Storage:** Redis with 24-hour TTL
- **Request hashing:**
  - Combines method, path, body, query params
  - SHA-256 hash for cache key
- **Response caching:**
  - Stores status code, headers, body
  - Returns cached response for duplicate requests
- **Use cases:**
  - Prevent duplicate reminders
  - Prevent duplicate calendar events
  - Prevent duplicate document uploads
  - Handle network retries safely
- **Bypass:** Skip cache if different idempotency key provided

**Example:**
```bash
curl -X POST /api/v1/reminders \
  -H "Authorization: Bearer token" \
  -H "Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{"title": "Test", "due_at_utc": "..."}'
```

---

### 23. Tool Calling System
**Module:** `app/api/tools/*.py`

**Technical Capabilities:**
- **Tool definitions:**
  - Calendar tools (create_event, update_event, delete_event)
  - Reminder tools (create_reminder, update_reminder, snooze_reminder)
  - Task tools (create_task, update_task, complete_task)
  - Search tools (search_knowledge_base)
- **Tool execution:**
  - Async execution
  - Error handling with try/catch
  - Result formatting
  - User isolation (all tools require user_id)
- **LLM integration:**
  - OpenAI function calling format
  - Anthropic tool use format
  - Automatic format conversion
- **Safety:**
  - Tool validation before execution
  - User permission checks
  - Rate limiting (inherits from API)

**Tool Format (OpenAI):**
```json
{
  "type": "function",
  "function": {
    "name": "create_reminder",
    "description": "Create a new reminder",
    "parameters": {
      "type": "object",
      "properties": {
        "title": {"type": "string"},
        "due_at_utc": {"type": "string", "format": "date-time"}
      },
      "required": ["title", "due_at_utc"]
    }
  }
}
```

---

## Infrastructure & Deployment

### 24. Docker Architecture
**Files:** `Dockerfile.prod`, `Dockerfile.dev`, `docker-compose.yml`

**Technical Capabilities:**
- **Multi-stage builds** (production):
  - Stage 1: Node.js (frontend build)
  - Stage 2: Python (backend + static frontend)
- **Development mode:**
  - Hot reload for frontend (Vite dev server)
  - Hot reload for backend (FastAPI `--reload`)
  - Volume mounts for code
- **Production mode:**
  - Optimized single-stage deployment
  - Frontend built and served from FastAPI
  - Single endpoint (port 8000)
- **Services:**
  - **orchestrator** - FastAPI API server
  - **worker** - Celery background worker
  - **beat** - Celery beat scheduler
  - **postgres** - PostgreSQL 15 database
  - **redis** - Redis 7 message broker/cache
  - **qdrant** - Qdrant vector database
  - **frontend** - Vite dev server (dev mode only)
- **Security:**
  - Non-root user (`brainda:1000`)
  - Init system (prevents zombie processes)
  - Default seccomp profile
  - Read-only root filesystem (where possible)
  - Resource limits (memory, CPU)

**Volume Mounts:**
- `/vault` - Note files
- `/uploads` - Document storage
- `/memory_vault` - OpenMemory markdown mirror
- `postgres_data` - PostgreSQL data persistence
- `qdrant_data` - Qdrant vector storage

---

### 25. Database Migrations
**Module:** `common/migrations.py`, `migrations/*.sql`

**Technical Capabilities:**
- **Auto-apply on startup:**
  - Runs before FastAPI starts
  - Idempotent (safe to re-run)
  - Ordered by filename (001, 002, 003...)
- **Migration tracking:**
  - `schema_migrations` table
  - Records applied migrations with timestamp
- **Transaction safety:**
  - Each migration runs in a transaction
  - Rollback on failure
- **Migration files:**
  - SQL files in `/migrations/`
  - Naming: `NNN_description.sql`
  - Currently: 006 migrations (up to multi-user auth)

**Migration Table:**
```sql
schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TIMESTAMP DEFAULT NOW()
)
```

**Recent Migrations:**
- `001_initial_schema.sql` - Core tables
- `002_add_recurrence.sql` - RRULE support
- `003_add_documents.sql` - Document ingestion
- `004_add_categories.sql` - Category system
- `005_add_calendar_reminders.sql` - Calendar-reminder linking
- `006_add_multi_user_auth.sql` - Multi-user, sessions, passkeys, TOTP

---

### 26. Health Checks & Readiness
**Module:** `app/api/main.py`, Docker Compose

**Technical Capabilities:**
- **Health endpoint:** `/api/v1/health`
  - Returns 200 OK if service is healthy
  - Checks: Database connection, Redis connection, Qdrant connection
  - Response: `{"status": "ok", "timestamp": "..."}`
- **Docker health checks:**
  - Interval: 30s (orchestrator), 10s (postgres, redis, qdrant)
  - Timeout: 10s (orchestrator), 5s (others)
  - Retries: 5
  - Start period: N/A
- **Service dependencies:**
  - Orchestrator waits for postgres, redis, qdrant
  - Worker waits for postgres, redis, qdrant
  - Beat waits for postgres, redis
- **Graceful shutdown:**
  - SIGTERM handling
  - Connection cleanup
  - In-flight request completion

---

### 27. Environment Configuration
**File:** `.env.example`

**Configuration Categories:**
- **Database:** PostgreSQL connection, credentials
- **Redis:** Redis connection URL
- **Qdrant:** Qdrant URL
- **Authentication:** API tokens, secrets
- **CORS:** Allowed origins
- **LLM:** Provider selection, API keys, models
- **Worker:** Celery concurrency
- **Google Calendar:** OAuth credentials, encryption keys
- **Data Retention:** Retention periods (days)
- **Rate Limiting:** Request limits, window sizes
- **Circuit Breakers:** Max failures, reset timeout
- **OpenMemory:** URL, API key, enable/disable
- **Memory Vault:** Sync enable, path

**Security Notes:**
- **Never commit `.env` to git** (use `.env.example` as template)
- **Generate strong secrets:** Use `openssl rand -hex 32` or similar
- **Rotate keys regularly:** Especially production tokens
- **Use environment-specific configs:** Different `.env` per environment

---

## Observability & Monitoring

### 28. Structured Logging
**Module:** `structlog` configuration in `main.py`

**Technical Capabilities:**
- **Format:** JSON (parseable by log aggregators)
- **Fields:**
  - `timestamp` - ISO 8601 format
  - `logger` - Logger name
  - `level` - Log level (DEBUG, INFO, WARNING, ERROR)
  - `event` - Event name (snake_case)
  - `...` - Context-specific fields
- **Log levels:**
  - DEBUG - Verbose debugging information
  - INFO - General information (default)
  - WARNING - Warning messages
  - ERROR - Error messages with stack traces
- **Context binding:**
  - User ID, request ID
  - Database query details
  - Task execution metadata
- **Examples:**
  ```json
  {
    "timestamp": "2025-11-18T12:34:56Z",
    "logger": "app.api.routers.reminders",
    "level": "info",
    "event": "reminder_created",
    "user_id": "uuid",
    "reminder_id": "uuid",
    "due_at_utc": "2025-11-19T10:00:00Z"
  }
  ```

**Configuration:**
```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

---

### 29. Prometheus Metrics
**Module:** `app/api/metrics.py`, `/api/v1/metrics` endpoint

**Technical Capabilities:**
- **Metric types:**
  - **Counter:** Monotonically increasing (e.g., requests, errors)
  - **Histogram:** Distributions (e.g., latencies, durations)
  - **Gauge:** Point-in-time values (e.g., queue depth, connections)
- **Available metrics:**
  - `api_request_duration_seconds` - Request latency (histogram)
    - Labels: method, endpoint, status_code
  - `chat_turns_total` - Chat message count (counter)
    - Labels: user_id
  - `tool_calls_total` - Tool invocation count (counter)
    - Labels: tool_name, status
  - `celery_queue_depth` - Tasks in queue (gauge)
    - Labels: queue_name
  - `embedding_duration_seconds` - Embedding time (histogram)
    - Labels: source_type
  - `vector_search_duration_seconds` - Search latency (histogram)
  - `documents_ingested_total` - Successful ingestions (counter)
  - `documents_failed_total` - Failed ingestions (counter)
  - `document_ingestion_duration_seconds` - Processing time (histogram)
  - `chunks_created_total` - Document chunks (counter)
  - `reminders_created_total` - Reminder creation (counter)
  - `reminders_deduped_total` - Deduplicated reminders (counter)
  - `retention_cleanup_total` - Cleaned items (counter)
    - Labels: data_type
  - `postgres_connections` - DB connection pool (gauge)
  - `redis_memory_bytes` - Redis memory usage (gauge)
  - `qdrant_points_count` - Vector count (gauge)
- **Scraping:**
  - Endpoint: `/api/v1/metrics`
  - Format: Prometheus text exposition format
  - No authentication required (metrics endpoint)

**Prometheus Configuration (example):**
```yaml
scrape_configs:
  - job_name: 'brainda'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/metrics'
    scrape_interval: 15s
```

---

### 30. Error Tracking & Debugging
**Module:** Various error handlers

**Technical Capabilities:**
- **Exception handling:**
  - Try-catch blocks in all critical paths
  - Proper error propagation
  - Structured error logging
- **Error context:**
  - User ID, request ID
  - Stack traces (ERROR level)
  - Input parameters
- **User-facing errors:**
  - Sanitized error messages
  - No sensitive data in responses
  - Clear error codes
- **Debugging tools:**
  - `/api/v1/health` - Service health
  - `/api/v1/metrics` - Prometheus metrics
  - Docker logs: `docker compose logs -f orchestrator`
  - Database queries: `docker exec -it brainda-postgres psql -U vib`
  - Redis inspection: `docker exec -it brainda-redis redis-cli`
  - Qdrant inspection: `curl http://localhost:6333/collections`

---

## Testing & Quality Assurance

### 31. Integration Test Suite
**Module:** `tests/stage_runner.sh`, `tests/stage*.sh`

**Technical Capabilities:**
- **Test stages:**
  - **Stage 0:** Health and metrics validation
  - **Stage 1:** Notes + vector search
  - **Stage 2:** Reminders + scheduler
  - **Stage 3:** Documents + RAG
  - **Stage 4:** Metrics validation
  - **Stage 5:** Idempotency testing
  - **Stage 6:** Calendar events + RRULE
  - **Stage 7:** Google Calendar sync
  - **Stage 8:** Multi-user auth (passkeys + TOTP)
- **Test utilities:**
  - `common.sh` - Shared functions (assert, wait_for, psql_query)
  - Temporary directories under `/tmp/vib-test-*`
  - Cleanup after each test run
- **Test execution:**
  - Sequential stage execution
  - Verbose output with `--verbose` flag
  - Individual stage testing with `--stage N`
  - All stages with `--all` flag
- **Prerequisites:**
  - `jq` - JSON parsing
  - `curl` - HTTP requests
  - `docker` - Container management
  - `python3` or `bc` - Floating-point math

**Running Tests:**
```bash
# Run all stages
./tests/stage_runner.sh --all --verbose

# Run specific stage
./tests/stage_runner.sh --stage 3 --verbose
```

---

## Frontend Features

### 32. React Web Application
**Module:** `app/web/`

**Technical Capabilities:**
- **Framework:** React 18 with TypeScript
- **Build tool:** Vite 7 (fast HMR, optimized builds)
- **Routing:** React Router v6
- **State management:**
  - React hooks (useState, useEffect, useContext)
  - Custom hooks (useChat, useConversation, useChatConversations)
  - Window-based communication (chat history sidebar)
- **Styling:** CSS Modules + CSS Variables
- **Responsive design:**
  - Mobile-first approach
  - Breakpoints: Mobile (<768px), Tablet (768-1023px), Desktop (≥1024px)
  - Touch gestures (swipe to close sidebar)
- **Components:**
  - Shared: Button, Input, Modal, LoadingSpinner, Toast
  - Chat: MessageBubble, ChatInput, MessageList, VoiceRecorder
  - Calendar: MonthlyCalendar, WeeklyCalendar, EventCard
  - Documents: DocumentUpload, DocumentViewer, DocumentCard
  - Layout: Sidebar, Header, MobileNav
- **Features:**
  - Hot reload (Vite HMR)
  - TypeScript type checking
  - CSS Modules for scoped styles
  - Dark mode support (CSS variables)
  - Error boundaries
  - Toast notifications
  - Keyboard shortcuts (Cmd+K / Ctrl+K for search)

**Development:**
```bash
cd app/web
npm install
npm run dev      # Dev server with HMR
npm run build    # Production build
npm run preview  # Preview production build
```

---

### 33. Progressive Web App (PWA) Features
**Status:** Not yet implemented

**Planned Capabilities:**
- Service worker for offline support
- App manifest for install prompt
- Push notifications for reminders
- Background sync for offline changes
- Cached assets for faster load times

---

## Performance & Scalability

### 34. Caching Strategy

**Technical Capabilities:**
- **Application-level caching:**
  - `@lru_cache` for infrastructure objects
  - Qdrant client singleton
  - Embedding service singleton
  - LLM adapter singletons
- **Redis caching:**
  - Idempotency keys (24h TTL)
  - Session tokens (30-day TTL)
  - Rate limit counters (sliding window)
- **Database connection pooling:**
  - asyncpg connection pool
  - Min connections: 5
  - Max connections: 20
- **Vector DB caching:**
  - Qdrant internal caching
  - No application-level caching (user isolation)

**Configuration:**
```bash
REDIS_URL=redis://redis:6379/0
# Redis maxmemory: 256MB
# Redis eviction policy: allkeys-lru
```

---

### 35. Horizontal Scaling Considerations

**Current Architecture:**
- **Stateless API servers** - Can scale horizontally
- **Worker pool** - Can scale horizontally (Celery workers)
- **Single scheduler** - Only one beat instance (Redis lock)
- **PostgreSQL** - Single instance (can use read replicas)
- **Redis** - Single instance (can use Redis Cluster)
- **Qdrant** - Single instance (can use Qdrant distributed mode)

**Scaling Recommendations:**
- Add more orchestrator replicas behind load balancer
- Add more Celery worker instances
- Use PostgreSQL read replicas for read-heavy queries
- Use Redis Sentinel for HA
- Use Qdrant distributed cluster for large vector datasets
- Consider object storage (S3) for document files

---

## Summary

**Total Features Documented:** 35 major features

**Technology Stack:**
- **Backend:** Python 3.11, FastAPI, asyncpg, Celery
- **Frontend:** React 18, TypeScript, Vite 7
- **Database:** PostgreSQL 15
- **Vector DB:** Qdrant
- **Cache/Queue:** Redis 7
- **Deployment:** Docker Compose
- **ML:** sentence-transformers, Whisper, OpenAI/Anthropic/Ollama
- **Auth:** Sessions, Passkeys (WebAuthn), TOTP

**Key Strengths:**
- ✅ Production-ready architecture
- ✅ Comprehensive security (user isolation, encryption, rate limiting)
- ✅ Modern AI capabilities (RAG, embeddings, tool calling)
- ✅ Scalable microservices design
- ✅ Excellent observability (metrics, logs, health checks)
- ✅ Multi-user support with advanced auth
- ✅ Extensive integration capabilities
- ✅ Strong code quality and documentation

---

**Last Updated:** 2025-11-18
**Maintained By:** Brainda Development Team
**License:** See LICENSE file
