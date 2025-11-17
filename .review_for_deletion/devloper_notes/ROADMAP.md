# ROADMAP.md

## Strategy

Deliver a solid MVP fast, then layer capabilities based on real usage. Each stage has: **Scope**, **Deliverables**, **Acceptance Criteria**, **Risk Checks**. No time estimates—progress is gated by acceptance criteria and shipping working software.

**Vibe coding principles**:
1. **Bias toward action** — Start coding with good-enough clarity
2. **Test as you build** — Create test data when you need it, not before
3. **Ship fast, learn faster** — Get to working software, then iterate
4. **Simplify ruthlessly** — MVP means minimum, not maximum

---

## Stage 0: Infrastructure & Deployment Foundation

### Scope
Infrastructure, Docker orchestration, service connectivity, simple auth, health checks, metrics foundation.

### Deliverables

### Database Changes

Create `init.sql` with initial schema:

```sql
-- Stage 0: Initial schema for infrastructure
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (single user for MVP)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    api_token TEXT UNIQUE NOT NULL,  -- Single token auth for MVP
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Devices table (for push notifications)
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,  -- web, ios, android
    push_token TEXT,
    push_endpoint TEXT,  -- for Web Push
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Feature flags
CREATE TABLE feature_flags (
    key TEXT PRIMARY KEY,
    enabled BOOLEAN DEFAULT FALSE,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for Stage 0
CREATE INDEX idx_devices_user ON devices(user_id);
CREATE INDEX idx_devices_token ON devices(push_token) WHERE push_token IS NOT NULL;

-- Insert default user (change token in production!)
INSERT INTO users (email, api_token) VALUES 
('user@example.com', 'default-token-change-me');
```
- [ ] Repo structure as per `/app` layout in README
- [ ] `docker-compose.yml` with all core services
  - orchestrator (FastAPI)
  - worker (Celery)
  - postgres (with initialization SQL)
  - redis (with maxmemory config: `maxmemory 256mb`, `maxmemory-policy allkeys-lru`)
  - qdrant (with performance tuning: `max_search_threads: 2`)
  - ollama (with model pre-download: `llama3.2` or similar)
  - unstructured
- [ ] `docker-compose.dev.yml` with overrides
  - Hot reload for development
  - Seed data loader (optional, create as needed)
- [ ] Reverse proxy config (Nginx Proxy Manager or Cloudflare Tunnel) OR localhost-only
- [ ] TLS working with valid cert (if internet-exposed) OR skip for localhost
- [ ] `.env.example` template with all required variables and comments
- [ ] Simple authentication:
  - **Option 1**: Single API token in `.env` (fastest, recommended for MVP)
  - **Option 2**: Basic email/password with bcrypt (if you prefer)
- [ ] Health endpoints: `/api/v1/health`, `/api/v1/version`
- [ ] Prometheus metrics endpoint: `/api/v1/metrics` (structure ready, counters can be empty)
- [ ] Structured logging middleware (JSON to stdout)
  - Include request_id, user_id, endpoint, duration
- [ ] Rate limiting middleware (Redis-backed, simple implementation)
- [ ] Database schema initialization script (`schema.sql` or Alembic migration)

### Acceptance Criteria
- [ ] `docker-compose up -d` starts all containers without errors
- [ ] All containers show "healthy" status within 60 seconds
- [ ] `/api/v1/health` returns `200 OK` with all service checks passing
- [ ] Metrics endpoint returns Prometheus-formatted data (even if counters are zero)
- [ ] Can authenticate with API token (send `Authorization: Bearer <token>`)
- [ ] All API requests log as JSON with required fields (request_id, user_id, endpoint, duration)
- [ ] Rate limiting triggers `429` after threshold exceeded (test with 35 rapid requests)
- [ ] Database initialized: `psql -c "\dt"` shows all tables from schema

### Risk Checks
- **Unraid networking**: Dedicated bridge network configured, no port conflicts
- **CORS**: Web + mobile origins whitelisted (even if mobile not built yet)
- **Secrets**: API token, DB password in `.env` (not hardcoded), never logged
- **Redis memory**: `maxmemory-policy allkeys-lru` prevents OOM

### Validation Script
```bash
#!/bin/bash
# smoke-test-stage0.sh

set -e

echo "Testing Stage 0..."

# Health check
curl -f http://localhost:8000/api/v1/health || exit 1
echo "✓ Health check passed"

# Metrics check
curl -f http://localhost:8000/api/v1/metrics | grep "# HELP" || exit 1
echo "✓ Metrics endpoint working"

# Auth check
TOKEN=$(grep API_TOKEN .env | cut -d= -f2)
curl -f -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/notes || exit 1
echo "✓ Authentication working"

# Rate limiting check
echo "Testing rate limiting..."
for i in {1..35}; do
    curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/chat > /dev/null
done
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/chat)
if [ "$STATUS" != "429" ]; then
    echo "✗ Rate limiting not working (got $STATUS, expected 429)"
    exit 1
fi
echo "✓ Rate limiting working"

# Database check
docker exec brainda-postgres psql -U postgres -d vib -c "\dt" | grep notes || exit 1
echo "✓ Database initialized"

echo "✅ Stage 0 validated - ready for Stage 1"
```

---

## Stage 1: Chat + Notes + Unified Vector + Simple Deduplication

### Scope
Chat interface with streaming, note creation via function calling, unified vector database, semantic search, file watcher, simple deduplication to prevent accidental duplicates.

### Deliverables

### Database Changes

Create `migrations/001_add_notes.sql`:

```sql
-- Stage 1: Notes, file sync, audit log, messages

-- Notes table
CREATE TABLE notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT,
    tags TEXT[] DEFAULT '{}',
    md_path TEXT UNIQUE,  -- relative to vault root
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- File sync state (tracks Markdown files for embeddings)
CREATE TABLE file_sync_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,  -- SHA256
    last_modified_at TIMESTAMPTZ NOT NULL,
    last_embedded_at TIMESTAMPTZ,
    embedding_model TEXT DEFAULT 'all-MiniLM-L6-v2:1',
    vector_id TEXT,  -- Qdrant point ID
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    action TEXT NOT NULL,
    old_value JSONB,
    new_value JSONB,
    source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat messages (optional)
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- CRITICAL: Deduplication constraint for notes
CREATE UNIQUE INDEX idx_notes_dedup ON notes (
    user_id, title, 
    (created_at::date), 
    (EXTRACT(hour FROM created_at)::int), 
    ((EXTRACT(minute FROM created_at)::int / 5)::int)
);

-- File sync constraint
CREATE UNIQUE INDEX idx_file_sync_path ON file_sync_state(user_id, file_path);

-- Performance indexes
CREATE INDEX idx_notes_user_id ON notes(user_id);
CREATE INDEX idx_notes_updated_at ON notes(updated_at);
CREATE INDEX idx_notes_created_at ON notes(user_id, created_at DESC);
CREATE INDEX idx_file_sync_user_path ON file_sync_state(user_id, file_path);
CREATE INDEX idx_file_sync_embedding_model ON file_sync_state(embedding_model);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_messages_user_created ON messages(user_id, created_at);
```

**Apply migration**:
```bash
docker exec brainda-postgres psql -U vib -d vib -f /app/migrations/001_add_notes.sql
```
- [ ] FastAPI `/api/v1/chat` endpoint with SSE streaming
- [ ] LLM adapter implementation (start with Ollama, make swappable)
- [ ] Function calling integration (single unified agent)
- [ ] Tool schema versioning (v1.0)
  - All tools return `{"schema_version": "1.0", "tool": "...", "parameters": {...}}`
- [ ] Tools implemented:
  - `create_note` (with 5-minute deduplication)
  - `update_note`
  - `search_notes`
- [ ] Simple deduplication for notes and reminders:
  ```python
  # Check for duplicate in last 5 minutes before creating
  existing = db.query(Note).filter(
      Note.user_id == user_id,
      Note.title == title,
      Note.created_at > now() - timedelta(minutes=5)
  ).first()
  if existing:
      return existing
  ```
- [ ] Markdown file creation in `/vault/notes` with YAML front-matter
  - UUID in front-matter (stable reference)
  - Slug-based filename with collision handling
- [ ] File watcher (Celery task) with 30s debounce
  - Watches `/vault` for changes
  - Triggers re-embedding on file modification
- [ ] `file_sync_state` table with content hashing and `embedding_model` tracking
- [ ] Unified Qdrant collection: `knowledge_base`
  - Payload includes `embedding_model`, `content_type`, all metadata from README
- [ ] Embedding pipeline:
  - Batch processing (batch size 50)
  - Priority queue: new > query misses > stale
  - Content hash deduplication (don't re-embed identical content)
  - Local model: `all-MiniLM-L6-v2:1` (or similar)
- [ ] Web UI (Next.js):
  - Chat interface with streaming
  - Note list (paginated)
  - Search interface
- [ ] Tool parameter validation with Pydantic schemas
- [ ] Filename collision handling (slug + UUID8 suffix)
- [ ] Standard error envelope on all endpoints

### Test Data Creation (as needed)
- [ ] Create 10-20 sample notes manually via chat as you test
- [ ] Include variety: simple notes, notes with tags, notes with wiki-links
- [ ] Save in `/vault/notes` for future testing

### Acceptance Criteria
- [ ] User sends "Add a note titled 'Test' with content 'Hello'" → Markdown file created with valid YAML
- [ ] Note file includes `id` in front-matter, filename is `test.md`
- [ ] Note appears in semantic search within 60 seconds
- [ ] Search "hello" finds the note in top 3 results
- [ ] Creating duplicate note (same title within 5 minutes) → returns existing note, no duplicate created
- [ ] Obsidian can open `/vault`, edit notes without breaking system
- [ ] External edit in Obsidian: system detects change within 60s, re-embeds
- [ ] Tool call with invalid note_id returns clear error in standard envelope
- [ ] Two notes with title "Test" created 10 minutes apart → unique filenames: `test.md`, `test-a1b2c3d4.md`
- [ ] `file_sync_state` tracks `embedding_model = "all-MiniLM-L6-v2:1"`
- [ ] Metrics show `tool_calls_total{tool="create_note", status="success"}` incrementing

### Risk Checks
- **LLM hallucination**: Validate all tool parameters against DB before execution
- **File sync race**: Atomic writes with temp file + rename, debounce prevents thrashing
- **Embedding cost**: Local model by default, content hash prevents re-embedding
- **Vector payload size**: Monitor average payload size, add compression if >10KB typical

### Validation Script
```bash
#!/bin/bash
# test-stage1.sh

set -e
TOKEN=$(grep API_TOKEN .env | cut -d= -f2)

echo "Testing Stage 1..."

# Test 1: Create note via chat
echo "Test 1: Creating note..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Add note titled TestNote with content Hello Brainda"}')
echo "Response: $RESPONSE"

# Test 2: Verify file exists
echo "Test 2: Checking file creation..."
ls /vault/notes/testnote.md || exit 1
echo "✓ File created"

# Test 3: Edit file externally
echo "Test 3: External edit..."
echo "Modified content" >> /vault/notes/testnote.md

# Test 4: Wait for re-embedding
echo "Waiting 60s for re-embedding..."
sleep 60

# Test 5: Check file_sync_state updated
echo "Test 5: Checking sync state..."
docker exec brainda-postgres psql -U postgres -d vib -c \
  "SELECT last_embedded_at, embedding_model FROM file_sync_state WHERE file_path = 'notes/testnote.md';" \
  | grep "all-MiniLM-L6-v2:1" || exit 1
echo "✓ Sync state updated"

# Test 6: Search finds note
echo "Test 6: Testing search..."
curl -s "http://localhost:8000/api/v1/search?q=hello" \
  -H "Authorization: Bearer $TOKEN" \
  | grep -i testnote || exit 1
echo "✓ Search working"

# Test 7: Deduplication test
echo "Test 7: Testing deduplication..."
RESPONSE1=$(curl -s -X POST http://localhost:8000/api/v1/notes \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title": "Duplicate Test", "body": "Content"}')
NOTE_ID=$(echo $RESPONSE1 | jq -r '.id')

RESPONSE2=$(curl -s -X POST http://localhost:8000/api/v1/notes \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title": "Duplicate Test", "body": "Content"}')
NOTE_ID2=$(echo $RESPONSE2 | jq -r '.id')

if [ "$NOTE_ID" != "$NOTE_ID2" ]; then
    echo "✗ Deduplication failed (got different IDs)"
    exit 1
fi
echo "✓ Deduplication working"

echo "✅ Stage 1 validated"
```

---

## Stage 2: Time Reminders + Push Notifications + SLO Tracking

### Scope
Create and fire time-based reminders, push notifications to web and mobile, delivery tracking, SLO measurement, simple deduplication.

### Deliverables

### Database Changes

Create `migrations/002_add_reminders.sql`:

```sql
-- Stage 2: Reminders, notifications, locations

-- Reminders table
CREATE TABLE reminders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    note_id UUID REFERENCES notes(id),  -- optional link
    title TEXT NOT NULL,
    body TEXT,
    due_at_utc TIMESTAMPTZ NOT NULL,
    due_at_local TIME NOT NULL,
    timezone TEXT NOT NULL,
    repeat_rrule TEXT,  -- NULL or RRULE string
    status TEXT DEFAULT 'active',  -- active, snoozed, done, cancelled
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Locations (for future geofencing)
CREATE TABLE locations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    lat NUMERIC(10, 7),
    lon NUMERIC(10, 7),
    radius_m INTEGER DEFAULT 100,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Notification delivery tracking
CREATE TABLE notification_delivery (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reminder_id UUID REFERENCES reminders(id),
    device_id UUID REFERENCES devices(id),
    sent_at TIMESTAMPTZ NOT NULL,
    delivered_at TIMESTAMPTZ,
    interacted_at TIMESTAMPTZ,
    action TEXT,  -- snooze, done, open
    status TEXT DEFAULT 'sent',  -- sent, delivered, failed
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- CRITICAL: Deduplication constraint for reminders
CREATE UNIQUE INDEX idx_reminders_dedup ON reminders (
    user_id, title, due_at_utc,
    (created_at::date),
    (EXTRACT(hour FROM created_at)::int),
    ((EXTRACT(minute FROM created_at)::int / 5)::int)
) WHERE status = 'active';

-- Performance indexes
CREATE INDEX idx_reminders_user_status ON reminders(user_id, status);
CREATE INDEX idx_reminders_due_at ON reminders(due_at_utc) WHERE status = 'active';
CREATE INDEX idx_notification_delivery_reminder ON notification_delivery(reminder_id);
CREATE INDEX idx_notification_delivery_device ON notification_delivery(device_id);
```
- [ ] `reminders` table with full schema (see README)
  - `due_at_utc`, `due_at_local`, `timezone`, `repeat_rrule`
- [ ] Tools implemented:
  - `create_reminder` (with 5-minute deduplication, schema v1.0)
  - `update_reminder` (schema v1.0)
  - `list_reminders`
  - `cancel_reminder`
  - `snooze_reminder`
- [ ] APScheduler integration
  - Redis-backed job store (or Postgres if preferred)
  - `replace_existing=True` for updates
  - Misfire grace time: 60 seconds
- [ ] Smart time parsing with defaults (see README)
  - "remind me to call the bank" → infer time based on current hour
  - "remind me tomorrow morning" → 9am next day
  - "remind me in 2 hours" → relative calculation
- [ ] RRULE parsing and validation
  - Use `python-dateutil` for parsing
  - Validation: max 2 years of recurrences (prevent infinite loops)
  - Basic unit tests for common patterns (daily, weekly, monthly)
- [ ] DST handling
  - On reminder fire: recalculate `due_at_utc` from `due_at_local + timezone`
  - Document DST behavior in code comments
- [ ] Notification gateway service (can be in orchestrator for MVP)
  - Web Push (VAPID keys in `.env` or Docker secrets)
  - FCM setup (Android) - credentials in `.env`
  - APNs setup (iOS) - credentials in `.env`
  - Unified send interface
- [ ] Push notification payload with TTL and actions (see README format)
  - TTL: 3600 seconds (1 hour)
  - Collapse key: `reminder:{id}`
  - Actions: Snooze 15m, Snooze 1h, Done, Open Chat
- [ ] `notification_delivery` tracking table
  - Record sent_at, delivered_at, interacted_at, action, status
- [ ] Device registration API: `POST /api/v1/devices/register`
- [ ] Web Push implementation
  - Service worker in Next.js
  - VAPID key generation (one-time setup)
  - Permission prompt flow
- [ ] Mobile push tokens (stub endpoints, full impl with mobile app in Stage 5)
- [ ] Retry logic for failed push sends (3 attempts with exponential backoff)
- [ ] Web UI: reminder list, upcoming view, create/edit forms, notification permission prompt
- [ ] Metrics for SLO tracking:
  - `reminder_fire_lag_seconds` histogram
  - `push_delivery_success_total` / `push_delivery_failure_total` counters
  - `reminders_deduped_total` counter
- [ ] Background job: cleanup old notification_delivery records (30 days)

### Timezone Test Creation (as you build)
- [ ] Create manual test reminders with different timezones:
  - "Remind me at 9am Asia/Riyadh tomorrow"
  - "Remind me at 3pm America/New_York tomorrow"
  - "Remind me every Monday at 8am UTC"
- [ ] Verify they fire at correct times
- [ ] Document any edge cases you discover

### Acceptance Criteria
- [ ] User says "Remind me at 5pm to call the bank" → reminder created with correct local time
- [ ] Push notification fires at exactly 17:00:00 local time (measured lag <5s)
- [ ] Notification includes title, body, and 4 action buttons
- [ ] Clicking Snooze 15m → reminder rescheduled, `notification_delivery` logged
- [ ] Clicking Done → reminder marked complete
- [ ] "Remind me every Monday at 9am" → RRULE generated, first reminder fires next Monday
- [ ] Creating duplicate reminder (same title, time within 5 minutes) → returns existing, no duplicate
- [ ] System restart: `docker restart brainda-orchestrator brainda-worker` → reminders still fire on schedule
- [ ] Failed push (device offline) → retries 3x with backoff, status="failed" in delivery table
- [ ] Metrics show `reminder_fire_lag_seconds` histogram with data
- [ ] Push delivery success rate measurable (need real device for accurate test)

### Risk Checks
- **Timezone complexity**: Store both UTC and local, test manually with multiple timezones
- **RRULE edge cases**: Start with simple patterns (daily, weekly), defer complex patterns (last Friday of month) to later
- **Push delivery reliability**: Retry logic with exponential backoff, delivery tracking
- **APScheduler durability**: Test restart scenarios, verify jobs persist

### Validation Script
```bash
#!/bin/bash
# test-stage2.sh

set -e
TOKEN=$(grep API_TOKEN .env | cut -d= -f2)

echo "Testing Stage 2..."

# Test 1: Create simple reminder (5 minutes from now)
echo "Test 1: Creating reminder..."
NOW_PLUS_5=$(date -u -d '+5 minutes' '+%Y-%m-%dT%H:%M:%SZ')
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/reminders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"Test reminder\",
    \"due_at_utc\": \"$NOW_PLUS_5\",
    \"due_at_local\": \"$(date -d '+5 minutes' '+%H:%M:%S')\",
    \"timezone\": \"UTC\"
  }")
REMINDER_ID=$(echo $RESPONSE | jq -r '.id')
echo "Created reminder: $REMINDER_ID"

# Test 2: Wait and check if it fires (manual verification needed)
echo "Reminder will fire in 5 minutes. Check browser/device for push notification."
echo "Press Enter after verifying notification received..."
read

# Test 3: Check notification_delivery table
echo "Test 3: Checking delivery log..."
docker exec brainda-postgres psql -U postgres -d vib -c \
  "SELECT status FROM notification_delivery WHERE reminder_id = '$REMINDER_ID';" \
  | grep -E "sent|delivered" || echo "Warning: No delivery record found (check if push is configured)"

# Test 4: Create recurring reminder
echo "Test 4: Creating recurring reminder..."
NEXT_MONDAY=$(date -u -d 'next monday 09:00' '+%Y-%m-%dT%H:%M:%SZ')
curl -s -X POST http://localhost:8000/api/v1/reminders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"Weekly standup\",
    \"due_at_utc\": \"$NEXT_MONDAY\",
    \"due_at_local\": \"09:00:00\",
    \"timezone\": \"UTC\",
    \"repeat_rrule\": \"FREQ=WEEKLY;BYDAY=MO\"
  }" | jq -r '.id'
echo "✓ Recurring reminder created"

# Test 5: Deduplication test
echo "Test 5: Testing deduplication..."
curl -s -X POST http://localhost:8000/api/v1/reminders \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"title\": \"Dup test\", \"due_at_utc\": \"$NOW_PLUS_5\", \"due_at_local\": \"12:00:00\", \"timezone\": \"UTC\"}" > /tmp/r1.json
sleep 2
curl -s -X POST http://localhost:8000/api/v1/reminders \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"title\": \"Dup test\", \"due_at_utc\": \"$NOW_PLUS_5\", \"due_at_local\": \"12:00:00\", \"timezone\": \"UTC\"}" > /tmp/r2.json

ID1=$(jq -r '.id' /tmp/r1.json)
ID2=$(jq -r '.id' /tmp/r2.json)
if [ "$ID1" != "$ID2" ]; then
    echo "✗ Deduplication failed"
    exit 1
fi
echo "✓ Deduplication working"

# Test 6: Check metrics
echo "Test 6: Checking metrics..."
curl -s http://localhost:8000/api/v1/metrics | grep reminder_fire_lag_seconds || echo "Warning: No fire lag data yet"
curl -s http://localhost:8000/api/v1/metrics | grep reminders_deduped_total || echo "Warning: No dedup metric yet"

echo "✅ Stage 2 validated (manual push verification required)"
```

---

## Stage 3: Document Ingestion + RAG + Structured Citations

### Scope
Upload PDFs/Docs, parse with Unstructured, chunk, embed into unified vector store, answer questions with structured citations.

### Deliverables

### Database Changes

Create `migrations/003_add_documents.sql`:

```sql
-- Stage 3: Documents and chunks for RAG

-- Documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    source TEXT,  -- upload, path
    storage_path TEXT NOT NULL,
    mime_type TEXT,
    sha256 TEXT,
    size_bytes BIGINT,
    status TEXT DEFAULT 'pending',  -- pending, processing, indexed, failed
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chunks table
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,  -- chunk sequence
    text TEXT NOT NULL,
    tokens INTEGER,
    metadata JSONB,  -- page, section, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Jobs table (for async processing)
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    type TEXT NOT NULL,  -- embed_document, sync_calendar, etc.
    status TEXT DEFAULT 'pending',
    payload JSONB,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Performance indexes
CREATE INDEX idx_documents_user_status ON documents(user_id, status);
CREATE INDEX idx_documents_sha256 ON documents(sha256);  -- dedup check
CREATE INDEX idx_chunks_document ON chunks(document_id, ordinal);
CREATE INDEX idx_jobs_status ON jobs(status, created_at);
CREATE INDEX idx_jobs_user ON jobs(user_id, created_at);
```
- [ ] `documents` and `chunks` tables (see README schema)
- [ ] `/api/v1/ingest` endpoint (multipart file upload)
  - File validation: size (<50MB), MIME type whitelist
  - SHA256 hash for deduplication (skip re-ingesting identical files)
  - Returns job_id immediately (async processing)
- [ ] Unstructured parser integration
  - Support: PDF, DOCX, TXT, MD (OCR optional, can defer)
  - Metadata extraction: filename, MIME, page numbers
- [ ] Chunking strategy
  - Recursive text splitter (~500 tokens per chunk, 50 token overlap)
  - Preserve paragraph/section boundaries when possible
- [ ] Job queue for ingestion (Celery task)
  - `jobs` table tracks status
  - Max 3 concurrent ingestion jobs (prevent resource exhaustion)
  - Simple progress: pending → running → completed/failed
- [ ] Vector upsert with full payload
  - `content_type: "document_chunk"`
  - `embedding_model` tracking
  - All metadata from README
- [ ] Search with content_type filtering
  - Query params: `content_type=note|document_chunk|all`
  - Simple score-based reranking (top-K by similarity)
- [ ] Structured citation format (see README)
  - Backend returns citations array
  - Frontend renders: `[VisaRules.pdf, p.12]` as clickable link
- [ ] Tool: `search_knowledge_base` (schema v1.0)
  - Parameters: query, content_type, limit
  - Returns: results with citations array
- [ ] Web UI:
  - File upload (drag/drop)
  - Job status indicator
  - Document library (list + delete)
  - Citation rendering in chat (clickable links)

### Test Data Creation (as you build)
- [ ] Find 3-5 test PDFs (mix of lengths: 5 pages, 20 pages, 50 pages)
- [ ] Include one with tables, one with images (if testing OCR)
- [ ] Save in `/tests/fixtures/` for future regression testing

### Acceptance Criteria
- [ ] Upload `test.pdf` (5 pages) → job_id returned immediately (<500ms)
- [ ] Job completes within 2 minutes for 20-page PDF
- [ ] Chunks created with correct ordinal sequence and page metadata
- [ ] Search "specific keyword from PDF" → relevant chunk in top 3
- [ ] User asks "What does the PDF say about X?" → answer with structured citations
- [ ] Citation format: `{"type": "document", "id": "...", "title": "test.pdf", "location": "p.5"}`
- [ ] Clicking citation in UI shows excerpt or opens viewer
- [ ] Large file (55MB) rejected with `413` and clear error message
- [ ] Unsupported file (.exe) rejected with `400` before processing
- [ ] Duplicate file (same SHA256) → skips ingestion, returns existing doc_id
- [ ] Failed parsing (corrupted PDF) → job status="failed", error_message populated
- [ ] Vector payloads include `embedding_model = "all-MiniLM-L6-v2:1"`

### Risk Checks
- **Parsing failures**: Graceful error handling, retryable via UI
- **Memory spikes**: Max 3 concurrent jobs, Celery task memory limits
- **Embedding backlog**: Priority queue ensures new docs processed first
- **Citation accuracy**: Validate citations against chunk metadata, log discrepancies

### Validation Script
```bash
#!/bin/bash
# test-stage3.sh

set -e
TOKEN=$(grep API_TOKEN .env | cut -d= -f2)

echo "Testing Stage 3..."

# Test 1: Upload PDF
echo "Test 1: Uploading test document..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/test-document.pdf")
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job created: $JOB_ID"

# Test 2: Wait for completion
echo "Test 2: Waiting for job completion..."
for i in {1..30}; do
    STATUS=$(curl -s "http://localhost:8000/api/v1/jobs/$JOB_ID" -H "Authorization: Bearer $TOKEN" | jq -r '.status')
    echo "Status: $STATUS"
    if [ "$STATUS" = "completed" ]; then
        break
    fi
    if [ "$STATUS" = "failed" ]; then
        echo "✗ Job failed"
        exit 1
    fi
    sleep 5
done

if [ "$STATUS" != "completed" ]; then
    echo "✗ Job did not complete in time"
    exit 1
fi
echo "✓ Job completed"

# Test 3: Verify chunks created
echo "Test 3: Checking chunks..."
DOC_ID=$(curl -s "http://localhost:8000/api/v1/jobs/$JOB_ID" -H "Authorization: Bearer $TOKEN" | jq -r '.result.document_id')
CHUNK_COUNT=$(docker exec brainda-postgres psql -U postgres -d vib -c \
  "SELECT COUNT(*) FROM chunks WHERE document_id = '$DOC_ID';" | grep -oP '\d+' | head -1)
echo "Chunks created: $CHUNK_COUNT"
if [ "$CHUNK_COUNT" -lt 1 ]; then
    echo "✗ No chunks created"
    exit 1
fi
echo "✓ Chunks created"

# Test 4: Search for content
echo "Test 4: Testing search..."
curl -s "http://localhost:8000/api/v1/search?q=test&content_type=document_chunk" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.results[0]' || echo "Warning: No results (might need better query)"

# Test 5: Chat with citation
echo "Test 5: Testing chat with citations..."
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "What does the document say?"}' \
  | grep -i citation || echo "Note: Check if LLM returns citations"

# Test 6: Reject large file
echo "Test 6: Testing file size limit..."
dd if=/dev/zero of=/tmp/large.pdf bs=1M count=55 2>/dev/null
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/large.pdf")
rm /tmp/large.pdf
if [ "$STATUS" != "413" ]; then
    echo "✗ Large file not rejected (got $STATUS)"
    exit 1
fi
echo "✓ File size limit enforced"

# Test 7: Duplicate detection
echo "Test 7: Testing duplicate detection..."
RESPONSE2=$(curl -s -X POST http://localhost:8000/api/v1/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/test-document.pdf")
DOC_ID2=$(echo $RESPONSE2 | jq -r '.document_id // .job_id')
echo "Second upload: $DOC_ID2"
# Should either return existing doc_id or skip ingestion

echo "✅ Stage 3 validated"
```

---

## Stage 4: Observability, Backups, Data Retention (Production Ready)

### Scope
Production-ready monitoring, backups, data lifecycle management. This is the LAST stage before MVP is considered "done" and ready for daily use.

### Deliverables
- [ ] Prometheus metrics fully populated (all metrics from README)
  - Verify all counters, histograms, gauges are emitting data
- [ ] Grafana dashboard templates (optional but recommended)
  - System dashboard: CPU, memory, disk, container health
  - Business dashboard: chat turns, tool calls, reminder fires
  - SLO dashboard: fire lag p95, push success rate
- [ ] Loki + Promtail (optional, can defer to post-MVP)
  - If not using: ensure logs are easily accessible via `docker logs`
- [ ] Alert rules (optional, can be email-based or simple)
  - Celery queue depth >100
  - Reminder fire lag p95 >10s
  - Push delivery success <95%
  - Disk usage >80%
- [ ] Automated Postgres backup script (`/backups/backup.sh`)
  - Nightly run (cron or systemd timer)
  - Atomic snapshots (see README)
  - 30-day retention
  - Sync to external storage (NAS, S3, or external drive)
- [ ] Automated Qdrant snapshot script
  - Weekly snapshots
  - 4-week retention
- [ ] Vault + uploads backup
  - Synced with Postgres/Qdrant (common timestamp)
- [ ] Restore playbook in `/docs/disaster-recovery.md`
  - Step-by-step instructions
  - Validation checklist
  - Test on fresh VM or Docker host
- [ ] Data retention implementation
  - Nightly Celery scheduled task
  - Messages: 90 days
  - Jobs: 30 days
  - Notification delivery: 60 days
  - Audit logs: 1 year
- [ ] Admin UI or CLI scripts (optional)
  - View jobs, retry failed
  - Trigger backup manually
  - View metrics

### Acceptance Criteria
- [ ] Metrics accessible at `/api/v1/metrics`, all key metrics have data
- [ ] Can query metrics with `curl http://localhost:8000/api/v1/metrics | grep reminder_fire_lag`
- [ ] Backup script runs successfully: `./backups/backup.sh`
- [ ] All backups labeled with timestamp: `backup-20250115-143022.dump`
- [ ] Backups stored in `/backups` and synced to external location
- [ ] Restore from backup works: fresh Docker setup → restore → health checks pass
- [ ] Data retention runs: old messages deleted after 90 days (test with fake old data)
- [ ] SLO metrics tracked: fire lag p95 <5s, push success >98% (over time)

### Risk Checks
- **Disk pressure**: Monitor disk usage, set up alerts at 80%
- **Backup corruption**: Test restore monthly, automate validation
- **Retention edge cases**: Don't delete recent data accidentally (test thoroughly)

### Validation Script
```bash
#!/bin/bash
# test-stage4.sh

set -e

echo "Testing Stage 4..."

# Test 1: Metrics
echo "Test 1: Checking metrics..."
curl -s http://localhost:8000/api/v1/metrics | grep -E "(reminder_fire_lag|push_delivery_success|tool_calls_total)" || exit 1
echo "✓ Metrics working"

# Test 2: Backup
echo "Test 2: Running backup..."
./backups/backup.sh
TIMESTAMP=$(date +%Y%m%d)
test -f /backups/postgres-$TIMESTAMP*.dump || exit 1
echo "✓ Backup created"

# Test 3: Simulate restore (optional, can be manual)
echo "Test 3: Testing restore (manual step)..."
echo "Run: docker-compose down && ./backups/restore.sh <timestamp> && docker-compose up -d"
echo "Verify health after restore"

# Test 4: Data retention
echo "Test 4: Testing retention (insert old data)..."
docker exec brainda-postgres psql -U postgres -d vib -c \
  "INSERT INTO messages (id, user_id, role, content, created_at) VALUES (gen_random_uuid(), (SELECT id FROM users LIMIT 1), 'user', 'old msg', NOW() - INTERVAL '100 days');"

# Run retention job (manual or via celery beat)
echo "Trigger retention job manually or wait for scheduled run"

# Verify old message deleted
REMAINING=$(docker exec brainda-postgres psql -U postgres -d vib -c \
  "SELECT COUNT(*) FROM messages WHERE created_at < NOW() - INTERVAL '90 days';" \
  | grep -oP '\d+' | head -1)
echo "Old messages remaining: $REMAINING (should be 0 after retention runs)"

echo "✅ Stage 4 validated - MVP is production-ready!"
echo ""
echo "🎉 Congratulations! You can now use Brainda daily."
echo "Next steps: Use it for 30 days, collect feedback, then prioritize Stage 5+"
```

---

## Post-MVP Stages (Prioritize Based on Usage)

After completing Stage 4, **use Brainda for 30 days yourself**. Track:
- What features do you use most?
- What's frustrating or missing?
- What would make it 10x better?

Then prioritize the stages below based on real usage patterns.

---

## Stage 5: Mobile App + Full Idempotency

### Scope
Native mobile app with offline support, full idempotency infrastructure for reliable sync.

### Why Now
Mobile introduces:
- Unreliable networks (retries)
- Offline mode (queue operations)
- Background tasks (notifications)

Full idempotency prevents duplicate data from retries.

### Deliverables
- [ ] Expo app (iOS + Android)
- [ ] Passkey authentication support (upgrade from API token)
- [ ] Chat, reminders, notes, search UIs
- [ ] Push notification handling (foreground, background, killed)
- [ ] Deep linking (`vib://reminders/{id}`)
- [ ] Offline queue (store failed requests, retry on connection)
- [ ] Full idempotency infrastructure:
  - `idempotency_keys` table
  - Middleware on all state-changing endpoints
  - 24-hour cache with automatic expiry
  - `Idempotency-Key` header on client
- [ ] Replace simple 5-minute deduplication with full idempotency

### Acceptance Criteria
- [ ] App works offline, queues operations, syncs when online
- [ ] Duplicate requests (same Idempotency-Key) return cached response
- [ ] No duplicate reminders/notes even with aggressive retries
- [ ] Push notifications work in all app states

---

## Stage 6: Calendar + Weekly Views

### Scope
Internal calendar with RRULE, weekly view, link reminders to events.

### Deliverables
- [ ] `calendar_events` table
- [ ] Tools: create/update/delete events
- [ ] RRULE expansion for display
- [ ] Weekly calendar view (web + mobile)
- [ ] Link reminders to events

### Acceptance Criteria
- [ ] "Create event every Monday 9am" → works
- [ ] Weekly view shows all instances
- [ ] Linking reminder to event works

---

## Stage 7: Google Calendar Sync

### Scope
OAuth, one-way sync to Google, optional two-way.

### Deliverables
- [ ] OAuth flow
- [ ] One-way sync (internal → Google)
- [ ] Optional two-way with conflict handling

---

## Stage 8: Advanced Authentication (Passkeys)

### Scope
WebAuthn for multi-user family hosting scenarios.

### Why Defer
- Single-user doesn't need this complexity
- API token or basic password is sufficient for MVP
- Add only when sharing with family members

### Deliverables
- [ ] Passkey registration and login
- [ ] TOTP backup for emergency recovery
- [ ] Multi-user support (organization_id)

---

## Stage 9: Location Reminders (High Risk)

### Decision Gate
Only if:
- [ ] 100+ users requesting it
- [ ] Battery testing complete (<5% drain)
- [ ] Privacy policy updated
- [ ] Fallback manual check implemented first

### Deliverables
- [ ] Geofencing on mobile
- [ ] Server validation
- [ ] Dwell time filtering

---

## Stage 10: Advanced Agent Routing

### Decision Gate
Only if:
- [ ] 6+ months usage data shows failure patterns
- [ ] Single agent accuracy <80% on specific tasks

### Deliverables
- [ ] Specialist agents (Reminders, Notes, KB, Calendar)
- [ ] Router (LLM-based or keyword)
- [ ] A/B testing framework

---

## Cross-Cutting Quality Gates

### Before Merging Any Feature:
- [ ] Unit tests for new code (aim for >70% coverage, don't obsess)
- [ ] Manual test script (copy/paste commands)
- [ ] API contract updated (if API changed)
- [ ] Schema change tested (forward and backward)
- [ ] Metrics added for new feature
- [ ] Error handling tested (what happens on failure?)
- [ ] Logs include context (user_id, entity_id, action)

### Performance Checks:
- [ ] API latency: p95 <500ms (normal load)
- [ ] Chat streaming: first token <1s
- [ ] Search: <200ms (up to 10K notes)
- [ ] Reminder fire: <5s from scheduled time (p95)

---

## Success Metrics (Post-MVP)

Track weekly:
- **Engagement**: Chat turns, tool calls, search queries
- **Reliability**: Reminder accuracy (>95% within 1min), push success (>98%)
- **Quality**: Search relevance (>80% top-3), tool success rate (>90%)
- **Retention**: Do you still use it? Daily? Weekly?

---

## Stage Timeline (Guidance Only)

| Stage | Focus | Estimated Effort | Can Skip? |
|-------|-------|------------------|-----------|
| 0 | Infrastructure | 1-2 weeks | No |
| 1 | Chat + Notes + Vector | 2-3 weeks | No |
| 2 | Reminders + Push | 2-3 weeks | No |
| 3 | Document RAG | 2-3 weeks | No |
| 4 | Observability + Backup | 1-2 weeks | No |
| 5 | Mobile + Idempotency | 3-4 weeks | Yes (if web-only) |
| 6 | Calendar | 2-3 weeks | Yes |
| 7 | Google Sync | 2-3 weeks | Yes |
| 8 | Passkeys | 2-3 weeks | Yes |
| 9 | Location | 3-4 weeks | Yes (high risk) |
| 10 | Specialist Agents | 3-4 weeks | Yes (premature) |

**Total MVP (Stages 0-4)**: 6-11 weeks for experienced solo developer

---

## Conclusion

**You have everything you need to start building.**

The docs are comprehensive but not perfect. They don't need to be. **The fastest way to improve them is to start coding and fix them as you discover gaps.**

**Your next action**: 
1. Run `docker-compose up -d` (start Stage 0)
2. Get health checks passing
3. Move to Stage 1

**Remember**:
- MVP = Stages 0-4 only
- Test data = create as you go, not upfront
- Ship fast, learn faster
- Use Brainda for 30 days before building Stage 5+

Good luck! 🚀
