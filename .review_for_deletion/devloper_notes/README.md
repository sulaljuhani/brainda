# README.md

## Project: Brainda — Chat-First Notes, Reminders & Knowledge Assistant

### One-liner

A self-hosted, chat-first personal assistant that lets you talk to your notes, set time reminders (location reminders post-MVP), and search your files using an LLM—backed by a Markdown vault (Obsidian-friendly) mirrored into a vector database.

---

## Vision & Goals

- **Chat is the UI**: "Remind me next Monday at 8:00", "Summarize this PDF and add it to notes."
- **Own your data**: All services run on your server (Unraid/Docker); Markdown is human-readable and portable.
- **Composable architecture**: Swap LLMs, embeddings, vector DB, or parsers with minimal friction.
- **Reliable nudges**: Time-based reminders delivered via push notifications on web and mobile.
- **RAG over your files**: Ingest PDFs/MD/Docs → semantic search + answer synthesis, with citations.

---

## Core Features

### MVP (initial release)

- Chat interface (web + mobile) with streaming responses
- Simple authentication (API token or basic password for self-hosted use)
- Time-based reminders (single and recurring via RRULE)
- Notes: create/update via chat; stored as Markdown files (Obsidian-friendly)
- Unified vector database: notes and documents searchable in one query
- Document ingestion (upload PDF/MD) → parse → chunk → embed → searchable
- Push notifications: Web Push + mobile (FCM/APNs) with TTL and collapse keys
- RAG: ask questions, get answers grounded in your notes/docs with structured citations
- Basic observability: metrics, structured logging, health checks, business SLOs
- Simple deduplication for reminders and notes (prevents accidental duplicates)
- Tool schema versioning for future-proof evolution

### Post-MVP (iterative additions)

- Advanced authentication (passkeys/WebAuthn for multi-user scenarios)
- Full idempotency infrastructure (for offline mobile sync)
- Internal calendar (weekly view), events with RRULE; optionally link reminders to events
- Google Calendar sync (one-way export → optional two-way sync with conflict handling)
- Location reminders (geofencing via mobile app) with clear limitations
- Advanced agent routing (multi-agent prompts) for specialized tasks
- Bi-directional Obsidian sync with conflict detection and safe backups
- Full observability stack (Grafana + Loki), audit logs, retention rules
- Role tools (email/contacts), reranking, metadata-aware RAG

---

## High-Level Architecture

```
[ Web (Next.js) ]  <—TLS—>  [ Reverse Proxy (NPM/Cloudflare Tunnel) ]  <—>  [ Orchestrator API (FastAPI) ]
[ Mobile (RN/Expo) ] ——push——>                                         |           |           |
                                                                        |           |           |
                                                                   [ Redis ]   [ Postgres ]  [ APScheduler ]
                                                                        |           |
                                                                   [ Celery Worker ]———> parsing/embeddings/RAG/sync
                                                                        |
                                                                   [ Qdrant (Vector DB) ]
                                                                        |
                                                                   [ Unstructured (parsers/OCR) ]
                                                                        |
                                                                   [ Files / Vault (Markdown + originals) ]

LLM backends via adapter: [ Ollama (default) ] or [ Gemini-CLI Worker ] or [ Claude proxy ]
Notifications: Web Push (VAPID), FCM/APNs through Notification Gateway
Metrics: Prometheus endpoint on Orchestrator
```

**Default LLM**: Local Ollama. External API calls (Gemini, Claude, OpenAI) are opt-in per request via UI toggle.

---

## Services (Dockerized)

- **orchestrator**: FastAPI app (tool execution + auth + API + metrics)
- **worker**: Celery worker for heavy/async jobs (ingestion, embeddings, RAG, sync)
- **postgres**: primary OLTP DB (users, devices, notes, reminders, calendar, documents, jobs)
- **redis**: Celery broker, ephemeral cache, rate limits
- **qdrant**: unified vector DB for semantic search over notes/docs
- **ollama**: local LLM runtime (default; adapter can target others)
- **unstructured**: parsing pipeline for PDFs/Docs/HTML/MD (+ OCR when needed)
- **notification-gateway**: unified sender for Web Push + FCM/APNs (could live in orchestrator)
- **reverse-proxy**: Nginx Proxy Manager or Cloudflare Tunnel (TLS + routing)
- **observability** (optional): Loki + Promtail + Grafana

> Mobile app (React Native/Expo) is built & shipped separately (not Docker), but talks to the orchestrator and registers for push.

---

## Key Concepts

### Function Calling Architecture (Simplified)

**MVP approach**: Single unified agent with native function calling
- Modern LLMs (Claude, GPT-4, Gemini) handle tool selection natively
- Orchestrator validates tool parameters and executes functions
- Clean separation: LLM decides *what* to do, orchestrator does *how*

**Available tools** (typed Pydantic schemas with versioning):
- `create_note`, `update_note`, `search_notes`
- `create_reminder`, `update_reminder`, `list_reminders`, `snooze_reminder`
- `search_knowledge_base`, `get_document_context`
- `create_calendar_event`, `update_calendar_event` (post-MVP)

**Tool contract with versioning**:
```json
{
  "schema_version": "1.0",
  "tool": "create_reminder",
  "parameters": {
    "title": "Call bank",
    "due_at_utc": "2025-11-05T17:00:00Z",
    "due_at_local": "17:00:00",
    "timezone": "Asia/Riyadh"
  }
}
```

### Tool Response Format (Standard Contract)

**All tools must return responses in this standardized format:**

**Success**:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "created_at": "2025-11-05T10:00:00Z",
    ...entity fields...
  }
}
```

**Deduplication (existing entity returned)**:
```json
{
  "success": true,
  "deduplicated": true,
  "data": {
    "id": "existing-uuid",
    "created_at": "2025-11-05T09:58:00Z",
    "message": "Note with this title already exists (created 2 minutes ago)"
  }
}
```

**Failure**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid timezone",
    "field": "timezone"
  }
}
```

**Error codes**:
- `VALIDATION_ERROR`: Invalid input parameter
- `NOT_FOUND`: Entity doesn't exist
- `PERMISSION_DENIED`: User doesn't own this entity
- `CONFLICT`: Would create duplicate (caught before DB)
- `INTERNAL_ERROR`: Unexpected server error

**Why this matters**: 
- Standardized responses prevent LLM hallucination of return formats
- The LLM knows exactly what shape to expect
- Error handling is consistent across all tools
- Deduplication is explicitly signaled (not hidden in success)

**Implementation example**:
```python
def tool_success(data: dict) -> dict:
    return {"success": True, "data": data}

def tool_dedup(data: dict, message: str) -> dict:
    return {"success": True, "deduplicated": True, "data": {**data, "message": message}}

def tool_error(code: str, message: str, field: str = None) -> dict:
    error = {"code": code, "message": message}
    if field:
        error["field"] = field
    return {"success": False, "error": error}
```

### Tool Schema Versioning Rules

Current version: `1.0`

**When to increment**:
- **Major (1.0 → 2.0)**: Remove parameter, change behavior incompatibly
- **Minor (1.0 → 1.1)**: Add optional parameter
- **Patch (1.0.0 → 1.0.1)**: Fix bug, no API change

**Examples**:
- Adding `tags` parameter (optional) to `create_note`: `1.0` → `1.1`
- Renaming `due_at` to `due_at_utc` in `create_reminder`: `1.0` → `2.0`
- Fixing timezone calculation bug: `1.0.0` → `1.0.1`

**Migration strategy**:
- Support last 2 major versions simultaneously
- Validate incoming `schema_version`, reject if unsupported
- Transform old format to new format in validation layer

**Implementation**:
```python
SUPPORTED_VERSIONS = ["1.0", "1.1", "2.0"]

def validate_tool_call(tool_call: dict) -> dict:
    version = tool_call.get("schema_version", "1.0")
    
    if version not in SUPPORTED_VERSIONS:
        raise UnsupportedVersionError(
            f"Schema version {version} not supported. "
            f"Supported versions: {SUPPORTED_VERSIONS}"
        )
    
    # Transform old versions to current format
    if version == "1.0" and tool_call["tool"] == "create_reminder":
        # v1.0 used "due_at", v2.0 uses "due_at_utc"
        if "due_at" in tool_call["parameters"]:
            tool_call["parameters"]["due_at_utc"] = tool_call["parameters"].pop("due_at")
    
    return tool_call
```

**Deprecation policy**:
- Announce deprecation 6 months before removal
- Log warnings when old versions used
- Remove support after 1 year
```

**Validation layer with simple deduplication**:
```python
@validate_tool_params
def create_reminder(title: str, due_at_utc: datetime, timezone: str, user_id: UUID):
    # Simple deduplication: check for identical reminder in last 5 minutes
    existing = db.query(Reminder).filter(
        Reminder.user_id == user_id,
        Reminder.title == title,
        Reminder.due_at_utc == due_at_utc,
        Reminder.created_at > datetime.utcnow() - timedelta(minutes=5)
    ).first()
    
    if existing:
        logger.info("duplicate_reminder_skipped", extra={"reminder_id": str(existing.id)})
        return existing  # Return existing instead of creating duplicate
    
    # Validate ownership and constraints
    if not is_valid_timezone(timezone):
        raise ToolParameterError("Invalid timezone")
    
    # Safe to proceed
    reminder = db.create(Reminder(
        user_id=user_id,
        title=title,
        due_at_utc=due_at_utc,
        timezone=timezone
    ))
    
    return reminder
```

**Post-MVP**: Full idempotency infrastructure (with `idempotency_keys` table and 24-hour cache) will be added in Stage 5 when building offline mobile sync.

---

### Unified Vector Store

**Single Qdrant collection**: `knowledge_base`

**Payload structure with namespacing**:
```json
{
  "embedding_model": "all-MiniLM-L6-v2:1",
  "content_type": "note | document_chunk",
  "source_id": "uuid-of-note-or-document",
  "title": "Human readable title",
  "tags": ["visa", "travel"],
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-20T14:00:00Z",
  "embedded_at": "2025-01-20T14:05:00Z",
  "parent_document_id": "uuid (for chunks only)",
  "chunk_index": 0,
  "user_id": "uuid"
}
```

**Benefits**:
- Single query searches everything
- Easy filtering: search only notes, only docs, or both
- Unified reranking across all sources
- Simpler sync logic
- Migration path when upgrading embedding models (filter by `embedding_model`, selectively re-embed)

**Embedding strategy**:
- Debounced batch processing (30s debounce, batch size 50)
- Content-based deduplication (hash-based cache)
- Priority queue: new documents > query misses > stale notes
- Progressive loading: first 3 chunks immediate, rest background
- Re-embedding: when model changes, filter by old `embedding_model` value and queue for update

---

### Markdown + Obsidian Compatibility

**File structure**:
```markdown
---
id: uuid-generated-by-system
title: Visa Rules Summary
tags: [visa, travel, uae]
created: 2025-01-15T10:30:00Z
updated: 2025-01-20T14:00:00Z
---

# Visa Rules Summary

Content here with [[wiki-links]] and #tags...
```

**Sync strategy** (pragmatic):
1. File watcher (Celery task) monitors `/vault` with 30s debounce
2. On change: check `file_sync_state` table (path, hash, timestamp)
3. If hash matches: skip (no actual change)
4. If conflict detected (external edit + pending system edit):
   - Create timestamped backup: `visa-rules-2025-01-20-140500.backup.md`
   - Let newer edit win
   - Show banner: "Note edited externally, backup saved"
5. Update `file_sync_state` and trigger re-embedding

**No 3-way merges**: Trust Obsidian users to manage their files; system is defensive with backups.

**Filename generation** (flat structure, Obsidian-friendly):
```python
def generate_markdown_filename(title: str) -> str:
    """
    Generates a URL-safe filename from title.
    Uses UID in YAML front-matter for stable references.
    Slug can change with title edits without breaking links.
    """
    slug = slugify(title)
    if exists(f"{vault_path}/{slug}.md"):
        slug = f"{slug}-{shortuuid.uuid()[:8]}"
    return f"{slug}.md"
```

**Note**: We use a flat structure by default (no YYYY/MM folders) to respect Obsidian conventions. Users can organize into folders manually if desired.

---

### Scheduling & Notifications

**Time-based reminders**:
- APScheduler creates durable jobs with `replace_existing`
- Store both UTC and local time:
  ```python
  reminders (
      due_at_utc TIMESTAMPTZ,      # For triggering
      due_at_local TIME,            # Original: "8am"
      timezone TEXT,                # "Asia/Riyadh"
      repeat_rrule TEXT             # NULL or RRULE string
  )
  ```
- On DST changes: recalculate `due_at_utc` from `due_at_local` + `timezone`
- On RRULE expansion: always recompute UTC from local + timezone at fire time to handle DST transitions correctly
- Worker sends push via notification gateway on fire

**Smart defaults**:
```python
# "Remind me to call the bank"
if now.hour < 14:
    suggest = today at 16:00
elif now.hour >= 17:
    suggest = next_business_day at 09:00
else:
    suggest = today at 17:00
```

**Notification payload with TTL and actions**:
```json
{
  "ttl_seconds": 3600,
  "collapse_key": "reminder:{reminder_id}",
  "priority": "high",
  "title": "Call the bank",
  "body": "Reminder set for 5:00 PM",
  "actions": [
    {"id": "snooze_15m", "title": "Snooze 15m"},
    {"id": "snooze_1h", "title": "Snooze 1h"},
    {"id": "done", "title": "Done"},
    {"id": "open", "title": "Open Chat"}
  ],
  "data": {
    "reminder_id": "uuid",
    "deep_link": "vib://reminders/{id}"
  }
}
```

**Push notification security**: VAPID keys and FCM/APNs credentials are stored as Docker secrets (or .env for development), scoped per user. Web Push endpoints are stored in the `devices` table with the push token. Never log push tokens or endpoints, as they can be used to send notifications to users.

**VAPID key generation** (one-time setup):
```bash
# Generate VAPID keys for Web Push
npx web-push generate-vapid-keys

# Add to .env:
# VAPID_PUBLIC_KEY=...
# VAPID_PRIVATE_KEY=...
# VAPID_SUBJECT=mailto:you@example.com
```

**Delivery tracking**:
```sql
notification_delivery (
    id, reminder_id, device_id,
    sent_at, delivered_at, interacted_at,
    status, error_message
)
```

---

### Standardized Citation Format

All citations follow a consistent structure for uniform UI rendering:

```json
{
  "answer": "Visa requirements include a valid passport and $50 fee.",
  "citations": [
    {
      "type": "document",
      "id": "doc_123",
      "title": "VisaRules.pdf",
      "chunk_index": 3,
      "location": "p.12",
      "excerpt": "Applicants must provide a valid passport..."
    },
    {
      "type": "note",
      "id": "note_456",
      "title": "Visa Notes",
      "section": "Key Points",
      "excerpt": "Fee is $50 for standard processing..."
    }
  ]
}
```

**UI rendering**:
- Inline citations: `[VisaRules.pdf, p.12]` as clickable link
- Hover: show excerpt preview
- Click: deep link to document viewer or note

---

### Calendar (Post-MVP)

**Internal calendar**:
- `calendar_events` table with RRULE for recurrence
- Weekly view in web + mobile
- Reminders can be linked to events

**Google Calendar sync** (optional):
- One-way export: internal → dedicated Google calendar
- OAuth2 flow with token refresh
- Optional two-way: pull changes, conflict policy uses `updated_at`
- Sync state tracked per user

---

## Data Model

### Core Tables

```sql
users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,  -- bcrypt hash (or NULL if using API token only)
    api_token TEXT UNIQUE,  -- for programmatic access
    created_at TIMESTAMPTZ DEFAULT NOW()
)

devices (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    platform TEXT,  -- web, ios, android
    push_token TEXT,
    push_endpoint TEXT,  -- for Web Push
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

notes (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    title TEXT NOT NULL,
    body TEXT,
    tags TEXT[],
    md_path TEXT UNIQUE,  -- relative to vault root
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)

reminders (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    note_id UUID REFERENCES notes,  -- optional link
    title TEXT NOT NULL,
    body TEXT,
    due_at_utc TIMESTAMPTZ NOT NULL,
    due_at_local TIME NOT NULL,
    timezone TEXT NOT NULL,
    repeat_rrule TEXT,  -- NULL or RRULE string
    status TEXT DEFAULT 'active',  -- active, snoozed, done, cancelled
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)

locations (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    name TEXT NOT NULL,
    lat NUMERIC(10, 7),
    lon NUMERIC(10, 7),
    radius_m INTEGER DEFAULT 100,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

documents (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    filename TEXT NOT NULL,
    source TEXT,  -- upload, path
    storage_path TEXT NOT NULL,  -- relative to /uploads
    mime_type TEXT,
    sha256 TEXT,
    size_bytes BIGINT,
    status TEXT DEFAULT 'pending',  -- pending, processing, indexed, failed
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)

chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents,
    ordinal INTEGER NOT NULL,  -- chunk sequence
    text TEXT NOT NULL,
    tokens INTEGER,
    metadata JSONB,  -- page, section, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
)

calendar_events (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    title TEXT NOT NULL,
    description TEXT,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ,
    timezone TEXT NOT NULL,
    location_id UUID REFERENCES locations,
    rrule TEXT,  -- NULL or RRULE string
    source TEXT DEFAULT 'internal',  -- internal, google
    google_event_id TEXT,
    status TEXT DEFAULT 'confirmed',  -- confirmed, tentative, cancelled
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)

calendar_sync_state (
    user_id UUID PRIMARY KEY REFERENCES users,
    google_calendar_id TEXT,
    sync_token TEXT,
    last_sync_at TIMESTAMPTZ,
    sync_enabled BOOLEAN DEFAULT FALSE
)

jobs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    type TEXT NOT NULL,  -- embed_document, sync_calendar, etc.
    status TEXT DEFAULT 'pending',  -- pending, running, completed, failed
    payload JSONB,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
)

messages (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    role TEXT NOT NULL,  -- user, assistant, system
    content TEXT NOT NULL,
    metadata JSONB,  -- tool calls, citations, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
)
```

### Essential Support Tables (MVP)

```sql
audit_log (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    entity_type TEXT NOT NULL,  -- note, reminder, document, etc.
    entity_id UUID NOT NULL,
    action TEXT NOT NULL,  -- create, update, delete
    old_value JSONB,
    new_value JSONB,
    source TEXT,  -- api, worker, sync, obsidian
    created_at TIMESTAMPTZ DEFAULT NOW()
)

file_sync_state (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    file_path TEXT NOT NULL,  -- relative to vault
    content_hash TEXT NOT NULL,  -- SHA256 of content
    last_modified_at TIMESTAMPTZ NOT NULL,
    last_embedded_at TIMESTAMPTZ,
    embedding_model TEXT,  -- Track which model was used
    vector_id TEXT,  -- Qdrant point ID
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, file_path)
)

notification_delivery (
    id UUID PRIMARY KEY,
    reminder_id UUID REFERENCES reminders,
    device_id UUID REFERENCES devices,
    sent_at TIMESTAMPTZ NOT NULL,
    delivered_at TIMESTAMPTZ,  -- platform confirmation
    interacted_at TIMESTAMPTZ,  -- user opened/dismissed
    action TEXT,  -- snooze, done, open
    status TEXT DEFAULT 'sent',  -- sent, delivered, failed
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

feature_flags (
    key TEXT PRIMARY KEY,
    enabled BOOLEAN DEFAULT FALSE,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
```

**Note**: The `idempotency_keys` table is deferred to Stage 5 (Mobile App with offline sync). For MVP, simple deduplication (5-minute window check) is sufficient.

### Critical Database Constraints

These constraints enforce correctness at the database level and prevent race conditions that application-level checks cannot catch.

```sql
-- ====================
-- DEDUPLICATION CONSTRAINTS
-- ====================
-- Prevents duplicate notes from retries (5-minute window)
CREATE UNIQUE INDEX idx_notes_dedup 
ON notes (
    user_id, 
    title, 
    (created_at::date), 
    (EXTRACT(hour FROM created_at)::int), 
    ((EXTRACT(minute FROM created_at)::int / 5)::int)
);

-- Prevents duplicate reminders from retries (5-minute window)
CREATE UNIQUE INDEX idx_reminders_dedup
ON reminders (
    user_id, 
    title, 
    due_at_utc,
    (created_at::date),
    (EXTRACT(hour FROM created_at)::int),
    ((EXTRACT(minute FROM created_at)::int / 5)::int)
)
WHERE status = 'active';

-- ====================
-- FILE SYNC CONSTRAINTS
-- ====================
-- One sync state per file per user (prevents duplicate entries)
CREATE UNIQUE INDEX idx_file_sync_path 
ON file_sync_state(user_id, file_path);

-- ====================
-- DEVICE CONSTRAINTS
-- ====================
-- One device registration per platform per user
CREATE UNIQUE INDEX idx_device_user_platform
ON devices(user_id, platform, push_token)
WHERE push_token IS NOT NULL;
```

**Why these constraints matter**:
- Application-level deduplication (5-minute check) catches most duplicates
- BUT: Race conditions can still create duplicates under high concurrency
- These DB constraints are the final safety net
- They work even if application logic fails or is bypassed
- The unique index will raise `UniqueViolation` exception, which you can catch and return the existing entity

**Example error handling**:
```python
try:
    note = await db.execute("INSERT INTO notes ...")
except UniqueViolation:
    # Race condition caught by DB constraint
    logger.warning("duplicate_note_prevented_by_constraint", title=title)
    # Fetch and return existing note
    existing = await db.fetchrow("""
        SELECT * FROM notes 
        WHERE user_id = $1 AND title = $2
        ORDER BY created_at DESC LIMIT 1
    """, user_id, title)
    return {"success": True, "deduplicated": True, "data": existing}
```

### Data Retention Policies

```sql
-- Automatic cleanup (run nightly via cron/scheduler)

-- Chat messages: keep 90 days
DELETE FROM messages WHERE created_at < NOW() - INTERVAL '90 days';

-- Jobs: keep 30 days
DELETE FROM jobs WHERE created_at < NOW() - INTERVAL '30 days';

-- Notification delivery logs: keep 60 days
DELETE FROM notification_delivery WHERE created_at < NOW() - INTERVAL '60 days';

-- Audit logs: keep 1 year (adjust based on compliance needs)
DELETE FROM audit_log WHERE created_at < NOW() - INTERVAL '1 year';
```

### Indexes

```sql
-- Critical indexes for performance
CREATE INDEX idx_notes_user_id ON notes(user_id);
CREATE INDEX idx_notes_updated_at ON notes(updated_at);
CREATE INDEX idx_notes_created_at ON notes(user_id, created_at DESC);
CREATE INDEX idx_reminders_user_status ON reminders(user_id, status);
CREATE INDEX idx_reminders_due_at ON reminders(due_at_utc) WHERE status = 'active';
CREATE INDEX idx_reminders_dedup ON reminders(user_id, title, due_at_utc, created_at);
CREATE INDEX idx_documents_user_status ON documents(user_id, status);
CREATE INDEX idx_chunks_document ON chunks(document_id, ordinal);
CREATE INDEX idx_calendar_events_user ON calendar_events(user_id, starts_at);
CREATE INDEX idx_jobs_status ON jobs(status, created_at);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_file_sync_user_path ON file_sync_state(user_id, file_path);
CREATE INDEX idx_file_sync_embedding_model ON file_sync_state(embedding_model);
CREATE INDEX idx_messages_user_created ON messages(user_id, created_at);
```

---

## API Surface (v1)

### Standard Error Envelope

All errors follow this format:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid due_at_utc format",
    "field": "due_at_utc",
    "details": {}
  }
}
```

**Error codes**:
- `VALIDATION_ERROR`: Invalid input
- `NOT_FOUND`: Resource doesn't exist
- `UNAUTHORIZED`: Auth required or failed
- `RATE_LIMITED`: Too many requests
- `CONFLICT`: Duplicate resource
- `INTERNAL_ERROR`: Server error

### Authentication

**MVP Options**:
1. **API Token** (simplest for self-hosted):
   ```http
   Authorization: Bearer <token-from-env>
   ```
2. **Basic Password**:
   ```http
   POST /api/v1/auth/login
   {"email": "you@example.com", "password": "..."}
   
   Response: {"session_token": "...", "expires_at": "..."}
   ```

**Post-MVP**: Passkeys (WebAuthn) for multi-user scenarios (Stage 7+)

### Pagination

All list endpoints use cursor-based pagination:
```http
GET /api/v1/notes?limit=50&cursor=eyJpZCI6IjEyMyJ9

Response:
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6IjE3MyJ9",
    "has_more": true
  }
}
```

### Chat
- `POST /api/v1/chat` (SSE stream) → tool calls + text response
  - Request: `{message: string, conversation_id?: UUID}`
  - Response: Server-Sent Events with `data: {type, content}`

### Notes
- `GET /api/v1/notes` → list notes (paginated, filterable by tags)
- `GET /api/v1/notes/{id}` → get note details
- `POST /api/v1/notes` → create note (deduplication via 5-minute window)
- `PATCH /api/v1/notes/{id}` → update note
- `DELETE /api/v1/notes/{id}` → soft delete

### Reminders
- `GET /api/v1/reminders` → list reminders (filterable by status, date range)
- `GET /api/v1/reminders/{id}` → get reminder details
- `POST /api/v1/reminders` → create reminder (deduplication via 5-minute window)
- `PATCH /api/v1/reminders/{id}` → update reminder
- `DELETE /api/v1/reminders/{id}` → cancel reminder
- `POST /api/v1/reminders/{id}/snooze` → snooze reminder
  - Body: `{duration_minutes: 15|60|1440}`

### Knowledge Base
- `POST /api/v1/ingest` → upload file for ingestion
  - Request: multipart form with `file` and optional `metadata`
  - Response: `{job_id: UUID, status: "pending"}`
- `GET /api/v1/search` → semantic search
  - Query params: `q`, `content_type`, `limit`, `min_score`
  - Response: `{results: [{id, title, excerpt, score, metadata, citations}]}`
- `GET /api/v1/documents` → list documents (paginated)
- `GET /api/v1/documents/{id}` → get document details + chunks

### Devices & Notifications
- `POST /api/v1/devices/register` → register push token
  - Request: `{platform, push_token, push_endpoint?}`
- `POST /api/v1/devices/{id}/unregister` → remove push token
- `POST /api/v1/notifications/test` → send test notification

### Calendar (Post-MVP)
- `GET /api/v1/calendar/events` → list events (weekly view by default)
- `POST /api/v1/calendar/events` → create event
- `PATCH /api/v1/calendar/events/{id}` → update event
- `DELETE /api/v1/calendar/events/{id}` → delete event
- `POST /api/v1/calendar/google/connect` → initiate OAuth flow
- `POST /api/v1/calendar/google/sync` → trigger manual sync

### System
- `GET /api/v1/health` → health check (includes DB, Redis, Qdrant status)
- `GET /api/v1/version` → API version info
- `GET /api/v1/metrics` → Prometheus metrics endpoint
- `GET /api/v1/feature-flags` → list enabled features

---

## Security & Privacy

### Authentication (MVP)

**Single API token approach** (simplest for self-hosted single-user):
- Token stored in `.env` file
- Clients send: `Authorization: Bearer <token>`
- Generate token: `openssl rand -hex 32`

**Setup**:
```bash
# In .env file
API_TOKEN=your-long-random-token-here-generate-with-openssl-rand-hex-32
```

**Validation**:
```python
API_TOKEN = os.getenv("API_TOKEN")

async def verify_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    
    token = authorization.split(" ")[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return token  # Valid
```

**Post-MVP upgrades** (defer these to later stages):
- **Stage 5**: Basic password auth (email + bcrypt) for family members
- **Stage 8**: Passkeys (WebAuthn) for multi-user scenarios
- **Never**: OAuth for third-party access (not needed for self-hosted)

**Why single token for MVP**:
- ✅ Simplest to implement (30 minutes)
- ✅ Secure enough for self-hosted internal use
- ✅ No database queries needed
- ✅ Easy to rotate (just change .env)
- ✅ Works with all clients (web, mobile, API)

**Security notes**:
- Keep token in `.env`, never commit to git
- Use `.env.example` with placeholder for reference
- Rotate token if compromised (restart services after changing)
- If exposing to internet, use TLS (Cloudflare Tunnel or Let's Encrypt)
```

### Authorization
- All endpoints scope by `user_id` from auth context
- Row-level security in queries
- No cross-user data leakage

### Network
- TLS terminated at reverse proxy
- Optional: Cloudflare Zero Trust for additional protection
- CORS configured for web + mobile origins

### Secrets Management
- Docker secrets for sensitive config
- No plaintext secrets in repo
- `.env.example` template with placeholders
- VAPID keys, FCM/APNs credentials stored as Docker secrets

### Data Handling
- Local LLM by default (Ollama)
- External API calls (Gemini, Claude, OpenAI) are opt-in per request via UI toggle
- User data never leaves server unless explicitly configured (e.g., Google Calendar sync)

### Rate Limiting
```python
RATE_LIMITS = {
    "/api/v1/chat": "30/minute per user",
    "/api/v1/ingest": "10/hour per user",
    "/api/v1/search": "60/minute per user",
}

# Circuit breaker for /chat
MAX_CONCURRENT_STREAMS_PER_USER = 2
```

### File Upload Validation
```python
MAX_FILE_SIZE = 50_MB
ALLOWED_MIMES = [
    "application/pdf",
    "text/markdown",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]
# Optional: ClamAV scanning for paranoid mode
```

---

## Backups & DR

### Automated Backups
- **Postgres**: nightly dumps with 30-day retention
  ```bash
  pg_dump -Fc db > backup-$(date +%Y%m%d).dump
  ```
- **Qdrant**: weekly snapshots via API
  ```bash
  curl -X POST http://qdrant:6333/collections/knowledge_base/snapshots
  ```
- **Vault + Uploads**: rsync or ZFS/BTRFS snapshots to external storage

### Atomic Snapshots
Single script that snapshots all three with a common timestamp:
```bash
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Brief table lock for consistency
psql -c "SELECT pg_start_backup('$TIMESTAMP');"
pg_dump -Fc db > /backups/postgres-$TIMESTAMP.dump
psql -c "SELECT pg_stop_backup();"

# Qdrant snapshot
curl -X POST http://qdrant:6333/collections/knowledge_base/snapshots \
  -H "Content-Type: application/json" \
  -d "{\"snapshot_name\": \"$TIMESTAMP\"}"

# Vault + uploads
rsync -a /vault /backups/vault-$TIMESTAMP/
rsync -a /uploads /backups/uploads-$TIMESTAMP/

echo "✅ Backup $TIMESTAMP complete"
```

### Restore Procedures
1. Fresh Unraid/Docker setup
2. Restore Postgres dump: `pg_restore -d db backup-TIMESTAMP.dump`
3. Restore Qdrant snapshot via API
4. Copy vault + uploads to mounted volumes
5. Run `docker-compose up`
6. Verify health endpoints

### Disaster Recovery Testing
- **Monthly drill**: restore to test VM, verify end-to-end functionality
- **Document**: step-by-step runbook in `/docs/disaster-recovery.md`

---

## Observability

### Business SLOs (Service Level Objectives)

Track these to measure user-facing reliability:

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Reminder fire latency (p95) | < 5 seconds | > 10 seconds |
| Push delivery success rate | > 98% | < 95% |
| Search result relevance | > 80% top-3 | Manual spot checks |
| API uptime | > 99.5% | < 99% |

### Metrics (Prometheus format)
```python
# Exposed at /api/v1/metrics
metrics = {
    # Business SLOs
    "reminder_fire_lag_seconds": histogram(
        buckets=[1, 5, 10, 30, 60, 300]
    ),
    "push_delivery_success_total": counter(labels=["platform"]),
    "push_delivery_failure_total": counter(labels=["platform", "error_type"]),
    
    # Business metrics
    "chat_turns_total": counter(labels=["user_id"]),
    "tool_calls_total": counter(labels=["tool_name", "status"]),
    "reminders_fired_total": counter(labels=["user_id"]),
    "reminders_deduped_total": counter(labels=["user_id"]),
    
    # Technical metrics
    "embedding_duration_seconds": histogram(labels=["source_type"]),
    "vector_search_duration_seconds": histogram(),
    "celery_queue_depth": gauge(labels=["queue_name"]),
    "postgres_connections": gauge(),
    "redis_memory_bytes": gauge(),
}
```

### Structured Logging
```python
# JSON logs to stdout (collected by Docker)
logger.info("reminder_created", extra={
    "user_id": str(user.id),
    "reminder_id": str(reminder.id),
    "reminder_type": "time",
    "due_at": due_at.isoformat(),
    "timezone": timezone,
})
```

### Health Checks
```python
GET /api/v1/health
{
    "status": "healthy",
    "timestamp": "2025-01-20T14:30:00Z",
    "services": {
        "postgres": "ok",
        "redis": "ok",
        "qdrant": "ok",
        "celery_worker": "ok"
    },
    "slos": {
        "reminder_fire_lag_p95": 3.2,
        "push_delivery_success_rate": 0.987
    }
}
```

### Post-MVP: Full Stack
- Loki for log aggregation
- Promtail for log shipping
- Grafana dashboards (system + business metrics + SLOs)

---

## Extensibility

### LLM Backends
```python
# Adapter pattern for LLM providers
class LLMAdapter(ABC):
    @abstractmethod
    def chat(self, messages, tools) -> ChatResponse:
        pass

# Implementations:
- OllamaAdapter (local, default)
- GeminiAdapter (API, opt-in)
- ClaudeAdapter (API, opt-in)
- OpenAIAdapter (API, opt-in)

# Switch via environment variable or per-request
LLM_BACKEND=ollama  # or gemini, claude, openai
```

### Embedding Models
```python
# Similar adapter for embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2  # local, default
EMBEDDING_MODEL=text-embedding-3-small  # OpenAI API, opt-in

# Migration strategy when upgrading models:
# 1. Deploy new model alongside old
# 2. Query file_sync_state WHERE embedding_model = 'old-model'
# 3. Queue for re-embedding with new model
# 4. Update embedding_model field after completion
```

### Storage Backends
```python
# Current: Local filesystem + Postgres + Qdrant
# Future: S3-compatible storage, alternative vector DBs
```

### Multi-User (Future)
- Add `organization_id` column to all user-scoped tables
- RBAC with roles: owner, admin, member
- Shared vaults with per-user views
- Upgrade to passkeys (WebAuthn) for secure multi-user auth

---

## Directory Layout

```
/app
  /api                      # FastAPI (orchestrator)
    main.py
    /routers
    /tools                  # Tool implementations
    /models                 # Pydantic schemas (versioned)
    /services               # Business logic
    /adapters               # LLM, embedding, storage adapters
  /worker                   # Celery tasks
    tasks.py
    /jobs                   # Job implementations
    /watchers               # File system watchers
  /web                      # Next.js app
    /app
    /components
    /lib
  /mobile                   # React Native/Expo app
    /src
    /app
  /deployment
    docker-compose.yml
    docker-compose.dev.yml  # Dev overrides with seed data
    env.example
    .dockerignore
  /infra
    /nginx-proxy-manager
    /cloudflare-tunnel
    /grafana-loki           # Optional observability
  /vault                    # Markdown notes (mounted volume)
  /uploads                  # Uploaded files (mounted volume)
  /backups                  # Backup scripts + storage (mounted)
    backup.sh               # Atomic snapshot script
  /docs
    architecture.md
    api-contracts.md
    disaster-recovery.md
    obsidian-conventions.md
  /tests
    /unit
    /integration
    /fixtures
  README.md
  ROADMAP.md
  LICENSE
```

---

## Non-Goals (for clarity)

- ❌ Multi-tenant SaaS (single-user or family-hosted only)
- ❌ Replacing Obsidian's editor UX (we embrace it, not compete)
- ❌ Background desktop indexer for entire OS (scope is vault + explicit uploads)
- ❌ Real-time collaborative editing (conflict resolution is backup-based)
- ❌ Mobile-first text editor (use Obsidian mobile or web interface)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **LLM hallucination on tool calls** | High | Validate all tool parameters against DB before execution; return clear errors |
| **Timezone complexity** | High | Store both UTC and local time; RRULE recomputation at fire time; comprehensive tests |
| **Markdown filename collisions** | Medium | Slug + short UUID suffix on conflict; audit log tracks all renames |
| **Embedding API costs** | Medium | Local embeddings by default; batch processing; content-based caching |
| **Push notification delivery gaps** | Medium | Retry logic with TTL; delivery tracking table; manual "check reminders" button as fallback |
| **File sync race conditions** | Medium | Debounced file watcher; atomic writes; backups before overwrites |
| **Qdrant performance on large vaults** | Low | Limit ingestion rate; HNSW index tuning; pagination on search results |
| **Mobile battery drain (geofencing)** | High | Defer to post-MVP; document limitations; offer manual location checks |
| **Duplicate reminders from retries** | Medium | Simple 5-minute deduplication window; upgrade to full idempotency in Stage 5 |

---

## Quick Start

### Default Stack (Swappable)

| Component | Default | Alternatives |
|-----------|---------|--------------|
| LLM | Ollama (llama3.2) | gpt-3.5-turbo, claude-3-5-haiku, gemini-pro |
| Embeddings | all-MiniLM-L6-v2 | text-embedding-3-small, gtebase |
| Vector DB | Qdrant | Weaviate, Milvus, Chroma |
| Task Queue | Celery + Redis | BullMQ, Temporal, Inngest |
| RDBMS | PostgreSQL | (no alternatives for MVP - stick with Postgres) |

**Why these defaults**:
- **Ollama**: Runs locally, free, no API costs, good privacy
- **all-MiniLM-L6-v2**: Fast, lightweight, runs on CPU, good quality
- **Qdrant**: Fast, easy setup, great filtering, good documentation
- **Celery + Redis**: Battle-tested, Python-native, easy to debug
- **PostgreSQL**: Rock-solid, JSONB support, great for hybrid workloads

**Swapping components**: Use the adapter pattern. Change `LLM_BACKEND` or `EMBEDDING_MODEL` in `.env`, restart services.
```

### Prerequisites
- Docker & Docker Compose
- Unraid (or any Docker host)
- 4GB+ RAM, 20GB+ storage
- Domain with TLS cert (or use Cloudflare Tunnel) OR localhost-only access

### Default Stack (Swappable)

| Component | Default | Alternatives |
|-----------|---------|--------------|
| LLM | Ollama (llama3.2) | gpt-3.5-turbo, claude-3-5-haiku |
| Embeddings | all-MiniLM-L6-v2 | text-embedding-3-small |
| Vector DB | Qdrant | Weaviate, Milvus |
| Task Queue | Celery + Redis | BullMQ, Temporal |
| RDBMS | PostgreSQL | (no alternatives for MVP) |

### Setup
```bash
# Clone repo
git clone <repo-url>
cd vib

# Copy environment template
cp deployment/env.example .env
# Edit .env with your settings:
# - Set API_TOKEN or configure email/password
# - Set VAPID keys for Web Push
# - Configure Ollama or external LLM API

# Start services
docker-compose up -d

# Check health
curl http://localhost:8000/api/v1/health

# Access web UI
open http://localhost:3000  # or https://your-domain.com
```

### First Steps
1. Login with API token or email/password
2. Register device for push notifications (click "Enable notifications")
3. Create first note: "Add a note titled 'Test' with content 'Hello Brainda'"
4. Set reminder: "Remind me in 5 minutes to check the system"
5. Upload test PDF: drag/drop in chat
6. Search: "What did I upload?"

---

## Demo Scenarios (MVP Validation)

**Scenario 1: Note Creation**
- User: "Add a note 'Visa rules summary' with bullets: valid 90 days, requires passport photo, costs $50"
- Expected: Markdown file created at `/vault/visa-rules-summary.md` with YAML front-matter, searchable immediately

**Scenario 2: Time Reminder**
- User: "Remind me today at 5pm to call the bank"
- Expected: Reminder created with correct timezone conversion, push notification fires at 17:00 local time (within 5s)

**Scenario 3: Document RAG**
- User uploads `VisaRules.pdf`
- User: "Summarize the visa requirements and add to notes"
- Expected: Document parsed, chunks embedded, answer cites structured format with page numbers, new note created with summary

**Scenario 4: Semantic Search**
- User: "Find my notes about travel documents"
- Expected: Returns relevant notes even without exact keyword match, ranked by relevance, top-3 accuracy >80%

**Scenario 5: Recurring Reminder**
- User: "Remind me every Monday at 9am to review my goals"
- Expected: RRULE generated, first reminder fires next Monday, subsequent Mondays scheduled automatically

**Scenario 6: Deduplication Test**
- User creates reminder: "Call bank at 5pm"
- Network glitch, user retries within 2 minutes
- Expected: Only one reminder created, second attempt returns existing reminder

---

## Contributing Guidelines

### Before Starting Work
1. Check `ROADMAP.md` for current stage priorities
2. Ensure tests pass: `pytest tests/`
3. Follow code style: `black` + `ruff`

### Pull Request Checklist
- [ ] Unit tests for new functions
- [ ] Integration test for new API endpoints
- [ ] Schema migration if DB changes (can be simple SQL file for MVP)
- [ ] Updated API docs in `/docs/api-contracts.md`
- [ ] Tool schema version incremented if changed
- [ ] Manual test scenario documented

### Commit Messages
```
feat(reminders): add RRULE validation
fix(sync): prevent race condition in file watcher
docs(api): update calendar endpoint examples
```

---

## Support & Troubleshooting

### Common Issues

**Push notifications not working:**
- Check device registration: `GET /api/v1/devices`
- Verify push tokens in database
- Test endpoint: `POST /api/v1/notifications/test`
- Check notification_delivery table for errors
- Verify VAPID keys set correctly in Docker secrets

**Search not finding notes:**
- Verify file_sync_state shows recent `last_embedded_at`
- Check `embedding_model` matches current model
- Manually trigger re-embedding: restart worker
- Check Qdrant collection: `curl http://qdrant:6333/collections/knowledge_base`

**Timezone issues:**
- Confirm `TZ` environment variable set correctly in `.env`
- Check `reminders.timezone` column matches user expectation
- Validate `due_at_utc` vs `due_at_local` calculation
- Review RRULE expansion for DST transitions

**Celery worker not processing jobs:**
- Check worker logs: `docker logs brainda-worker`
- Verify Redis connection: `redis-cli ping`
- Check queue depth: `celery -A worker inspect active`
- Review job retention (may be deleted after 30 days)

**Duplicate reminders created:**
- Check if retries happening within 5-minute window
- Verify deduplication index exists: `idx_reminders_dedup`
- Review logs for `duplicate_reminder_skipped` events
- If persistent, consider upgrading to full idempotency (Stage 5)

**Authentication issues:**
- API token: Verify `Authorization: Bearer <token>` header matches `.env`
- Password: Check bcrypt hash in database matches expected password
- Session expired: Re-login to get new session token

### Getting Help
- Check `/docs` folder for detailed guides
- Review audit_log table for debugging
- Enable DEBUG logging: `LOG_LEVEL=DEBUG` in `.env`
- Check Prometheus metrics for SLO violations

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for detailed stage breakdown and acceptance criteria.

---
