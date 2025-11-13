# File Watcher Implementation Analysis

## Executive Summary
The file watcher implementation that monitors the vault directory for external file changes and triggers re-embedding is located in `/home/user/brainda/app/worker/tasks.py`. It uses the `watchdog` library to monitor the `/vault` directory for markdown file modifications.

---

## 1. WHERE IS THE FILE WATCHER CODE?

### Primary Location
**File**: `/home/user/brainda/app/worker/tasks.py`
**Lines**: 526-598

### Key Components:

#### 1a. VaultWatcher Class (lines 527-542)
```python
class VaultWatcher(FileSystemEventHandler):
    def __init__(self, debounce_seconds=30):
        self.debounce_seconds = debounce_seconds
        self.pending_changes = {}
    
    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.md'):
            return
        
        filepath = event.src_path
        self.pending_changes[filepath] = time.time()
        
        schedule_embedding_check.apply_async(
            args=[filepath],
            countdown=self.debounce_seconds
        )
```

#### 1b. File Watcher Starter (lines 544-552)
```python
def start_file_watcher():
    path = "/vault"
    event_handler = VaultWatcher()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    logger.info("file_watcher_started", path=path)
```

#### 1c. Celery Hook (lines 593-598)
```python
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    import threading
    watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    watcher_thread.start()
```

---

## 2. HOW DOES IT DETECT FILE CHANGES?

### Detection Mechanism: Watchdog Library
- **Library**: `watchdog==3.0.0` (from requirements.txt line 14)
- **Implementation**: Uses `FileSystemEventHandler` from `watchdog.events`
- **Observer Pattern**: Uses the `Observer` class from `watchdog.observers`

### Detection Flow:

1. **Initialization** (on Celery startup):
   - `setup_periodic_tasks()` hook is called when Celery configures
   - Starts `start_file_watcher()` in a daemon thread
   - Creates an `Observer` that monitors `/vault` recursively

2. **File Change Detection**:
   - `on_modified()` callback triggered by OS file system events
   - Filters:
     - Skips if event is a directory
     - Only processes `.md` files
   - Records filepath and current timestamp in `pending_changes` dict

3. **Event Details**:
   - Event object contains:
     - `event.src_path`: Full path to modified file (e.g., `/vault/notes/test.md`)
     - `event.is_directory`: Boolean indicating if path is directory
     - Other watchdog event properties

---

## 3. HOW DOES IT TRIGGER RE-EMBEDDING?

### Task Chain Flow:

```
File Modification (OS Event)
    ↓
VaultWatcher.on_modified()
    ↓
schedule_embedding_check.apply_async(args=[filepath], countdown=30)
    ↓ [30 second debounce delay]
schedule_embedding_check task executes
    ├─ Read file from disk
    ├─ Calculate SHA256 hash of content
    ├─ Query database for existing content_hash
    └─ If changed:
        ├─ Extract note_id from frontmatter
        └─ Call embed_note_task.delay(note_id)
    ↓ [Immediate execution in Celery queue]
embed_note_task executes
    ├─ Fetch note from database
    ├─ Call embed_and_upsert_note_async()
    │   ├─ Generate embedding using EmbeddingService
    │   ├─ Upsert vector to Qdrant
    │   └─ Update file_sync_state with:
    │       ├─ content_hash
    │       ├─ last_embedded_at = NOW()
    │       └─ embedding_model
    └─ Update notes.updated_at = NOW()
```

### Key Task Functions:

#### schedule_embedding_check (lines 235-269)
```python
@celery_app.task(name='worker.tasks.schedule_embedding_check')
def schedule_embedding_check(filepath):
    """Check if file needs re-embedding after debounce period"""
    async def _async_check():
        relative_path = filepath.replace('/vault/', '')
        
        try:
            with open(filepath, 'r') as f:
                content = f.read()
        except FileNotFoundError:
            logger.warning("file_watcher_missing_file", path=filepath)
            return
        
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        conn = await _connect_db()
        try:
            existing = await conn.fetchrow("""
                SELECT content_hash, last_embedded_at 
                FROM file_sync_state 
                WHERE file_path = $1
            """, relative_path)
            
            if not existing or existing['content_hash'] != content_hash:
                logger.info("file_changed_externally", path=relative_path)
                
                note_id = extract_note_id_from_frontmatter(content)
                
                if note_id:
                    embed_note_task.delay(str(note_id))
                else:
                    logger.warning("no_note_id_in_frontmatter", path=relative_path)
        finally:
            await conn.close()
    asyncio.run(_async_check())
```

#### embed_note_task (lines 271-301)
```python
@celery_app.task(name='worker.tasks.embed_note_task')
def embed_note_task(note_id_str: str):
    """Background task to embed a note"""
    async def _async_embed():
        note_id = uuid.UUID(note_id_str)
        conn = await _connect_db()
        try:
            note = await conn.fetchrow("SELECT * FROM notes WHERE id = $1", note_id)
            if not note:
                logger.warning("embed_note_task_missing_note", note_id=note_id_str)
                return
            logger.info("embed_note_task_start", note_id=note_id_str, md_path=note['md_path'])
            try:
                await embed_and_upsert_note_async(
                    note['id'], note['title'], note['body'], note['tags'],
                    note['md_path'], note['user_id']
                )
                # Update note timestamp
                async with conn.transaction():
                    await conn.execute("""
                        UPDATE notes
                        SET updated_at = NOW()
                        WHERE id = $1
                    """, note_id)
                logger.info("embed_note_task_success", note_id=note_id_str, md_path=note['md_path'])
            except Exception as exc:
                logger.error("embed_note_task_failure", note_id=note_id_str, error=str(exc))
                raise
        finally:
            await conn.close()
    asyncio.run(_async_embed())
```

#### embed_and_upsert_note_async (lines 185-227)
```python
async def embed_and_upsert_note_async(note_id: uuid.UUID, title: str, body: str, 
                                       tags: list, md_path: str, user_id: uuid.UUID):
    """Embed note and store in Qdrant"""
    text = f"{title}\n\n{body}"
    logger.info("embedding_note_start", note_id=str(note_id), md_path=md_path)
    with embedding_duration_seconds.labels(source_type="note").time():
        embedding = await embedding_service.embed(text)
    
    client = QdrantClient(url=QDRANT_URL)
    ensure_qdrant_collection(client)
    client.upsert(
        collection_name="knowledge_base",
        points=[{...}]
    )
    logger.info("embedding_note_qdrant_upserted", note_id=str(note_id))

    # Update database in a transaction
    conn = await _connect_db()
    try:
        async with conn.transaction():
            await conn.execute("""
                INSERT INTO file_sync_state (user_id, file_path, content_hash, 
                    last_modified_at, last_embedded_at, embedding_model, vector_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id, file_path) DO UPDATE
                SET content_hash = $3, last_embedded_at = $5, vector_id = $7, 
                    updated_at = NOW()
            """, user_id, md_path, hash_content(text), datetime.now(timezone.utc), 
                datetime.now(timezone.utc), embedding_service.model_name, str(note_id))
        logger.info("embedding_note_db_upserted", note_id=str(note_id))
    finally:
        await conn.close()
```

---

## 4. WHY MIGHT IT NOT BE WORKING?

### Known Issues Identified:

#### Issue 1: Path String Manipulation Bug (CRITICAL)
**Location**: Line 239 in `schedule_embedding_check()`
```python
relative_path = filepath.replace('/vault/', '')
```

**Problem**: 
- The watchdog passes full path like `/vault/notes/example.md`
- This simple string replace works but is fragile
- If `/vault/` appears elsewhere in path, it breaks

**Example**:
- filepath = `/vault/notes/vault-topic-1.md`
- After replace: `notes/vault-topic-1.md` ✓ (works but accidental)
- filepath = `/vault/notes/my/vault/file.md`
- After replace: `notes/my/file.md` ✗ (BROKEN - removes extra /vault/)

**Impact**: For files with "vault" in their path names, the lookup fails silently.

#### Issue 2: Debounce Timing (TIMING SENSITIVITY)
**Location**: Line 528 in `VaultWatcher.__init__()`
```python
def __init__(self, debounce_seconds=30):
    self.debounce_seconds = debounce_seconds
```

**Problem**:
- 30-second debounce is hardcoded
- Test expects update within 180 seconds
- Test may not account for debounce delay + processing time

**Test Timeline** (from stage1.sh:127-137):
```bash
before=$(psql_query "SELECT extract(epoch FROM last_embedded_at) ...")
echo "\nUpdated $(date)" >> "$file"
wait_for "psql_query ... WHERE file_path = '$NOTE_FIXTURE_MD_PATH';" 180 "re-embedding..."
```

**Actual Timeline**:
```
0s   - File edited externally
30s  - schedule_embedding_check task starts (after debounce)
30s+ - Read file, check hash, extract note ID
30s+ - embed_note_task.delay() queued
30s+ - embed_note_task executes: embedding generation (2-5s), DB update
35s+ - last_embedded_at timestamp in database should be updated
```

**Expected**: Test checks immediately, but watcher has 30s debounce before even starting checks.

#### Issue 3: Observer Thread Lifecycle
**Location**: Lines 593-598 in `setup_periodic_tasks()`
```python
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    import threading
    watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    watcher_thread.start()
```

**Problem**:
- Observer is started in daemon thread
- Daemon threads are killed when main process exits
- If test timing is tight, observer might not be fully ready
- No explicit wait/join after starting observer

**Impact**: Race condition - test might start before observer is fully initialized.

#### Issue 4: Missing Error Handling
**Location**: Line 242 in `schedule_embedding_check()`
```python
try:
    with open(filepath, 'r') as f:
        content = f.read()
except FileNotFoundError:
    logger.warning("file_watcher_missing_file", path=filepath)
    return
```

**Problem**:
- File deleted between event and processing
- No other exceptions caught (encoding errors, permission issues, etc.)
- If exception occurs, task silently fails with no logging

#### Issue 5: Frontmatter Extraction Failure
**Location**: Line 261 in `schedule_embedding_check()`
```python
note_id = extract_note_id_from_frontmatter(content)

if note_id:
    embed_note_task.delay(str(note_id))
else:
    logger.warning("no_note_id_in_frontmatter", path=relative_path)
```

**Problem**:
- If frontmatter parsing fails or note_id is missing, re-embedding doesn't happen
- The warning is logged but task chain stops
- File content might have been modified but not re-embedded

#### Issue 6: Container Path Mismatch
**Location**: Lines 9, 102 in `docker-compose.yml`
```yaml
volumes:
  - ./vault:/vault  # Host ./vault -> Container /vault
```

**Problem**:
- Docker mounts host `./vault` to container `/vault`
- Watchdog must run in same container as mounted path
- Both orchestrator and worker containers mount the same path
- If file watcher runs in worker but API modifies in orchestrator, there's a race

---

## 5. RECOMMENDED FIXES

### Fix 1: Improve Path Handling
```python
# Use pathlib for safer path manipulation
from pathlib import Path

def schedule_embedding_check(filepath):
    """Check if file needs re-embedding after debounce period"""
    async def _async_check():
        # Better path handling
        vault_path = Path("/vault")
        try:
            file_path = Path(filepath)
            relative_path = str(file_path.relative_to(vault_path))
        except ValueError:
            logger.error("file_path_not_in_vault", filepath=filepath)
            return
        
        # ... rest of function
```

### Fix 2: Make Debounce Configurable
```python
class VaultWatcher(FileSystemEventHandler):
    def __init__(self, debounce_seconds=None):
        if debounce_seconds is None:
            debounce_seconds = int(os.getenv("FILE_WATCHER_DEBOUNCE", "30"))
        self.debounce_seconds = debounce_seconds
        self.pending_changes = {}
```

Then in `.env`:
```env
FILE_WATCHER_DEBOUNCE=5  # Faster for tests
```

### Fix 3: Add Observer Startup Verification
```python
def start_file_watcher():
    path = "/vault"
    event_handler = VaultWatcher()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    logger.info("file_watcher_started", path=path)
    
    # Give observer time to initialize
    time.sleep(0.5)
    
    if observer.is_alive():
        logger.info("file_watcher_verification_success")
    else:
        logger.error("file_watcher_failed_to_start")
```

### Fix 4: Better Exception Handling
```python
async def _async_check():
    # ... existing code ...
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        logger.warning("file_watcher_missing_file", path=filepath)
        return
    except UnicodeDecodeError:
        logger.error("file_watcher_encoding_error", path=filepath)
        return
    except IOError as e:
        logger.error("file_watcher_io_error", path=filepath, error=str(e))
        return
```

### Fix 5: Improve Frontmatter Handling
```python
if note_id:
    logger.info("file_change_queued_for_embedding", path=relative_path, note_id=str(note_id))
    embed_note_task.delay(str(note_id))
else:
    logger.error("file_change_skipped_no_note_id", path=relative_path, 
                 error="Could not extract note_id from frontmatter")
```

### Fix 6: For Testing - Reduce Debounce or Add Sleep
In `tests/stage1.sh` (lines 127-137):
```bash
external_edit)
    local before after file="vault/$NOTE_FIXTURE_MD_PATH" backup="$TEST_DIR/external-edit-$TIMESTAMP.md"
    cp "$file" "$backup"
    before=$(psql_query "SELECT extract(epoch FROM last_embedded_at) FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';")
    
    echo "\nUpdated $(date)" >> "$file"
    
    # Account for debounce delay: 30s + processing + buffer
    sleep 35
    
    # Then start checking
    wait_for "psql_query \"SELECT extract(epoch FROM last_embedded_at) FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';\" | awk -v before=$before 'NF && \$1 > before { exit 0 } END { exit 1 }'" 145 "re-embedding after external edit"
    
    after=$(psql_query "SELECT extract(epoch FROM last_embedded_at) FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';")
    assert_greater_than "${after:-0}" "${before:-0}" "Embedding timestamp advanced" || rc=1
    cp "$backup" "$file"
    rm -f "$backup"
    ;;
```

---

## 6. FILE STRUCTURE OVERVIEW

```
/home/user/brainda/
├── app/
│   ├── worker/
│   │   └── tasks.py                    # File watcher implementation (MAIN FILE)
│   │       ├── VaultWatcher class      # Lines 527-542
│   │       ├── start_file_watcher()    # Lines 544-552
│   │       ├── schedule_embedding_check()  # Lines 235-269
│   │       ├── embed_note_task()       # Lines 271-301
│   │       └── setup_periodic_tasks()  # Lines 593-598 (startup hook)
│   │
│   └── api/
│       ├── main.py                     # API endpoints that create/modify notes
│       │   ├── create_markdown_file()  # Lines 159-180 (creates files in /vault)
│       │   └── queue_embedding_task()  # Lines 284-287 (triggers embedding)
│       │
│       └── requirements.txt             # Dependencies (watchdog==3.0.0)
│
├── docker-compose.yml                  # Volume mount: ./vault:/vault (lines 9, 102)
├── tests/
│   └── stage1.sh                       # Test with external_edit case (lines 127-137)
│
└── vault/                              # Directory monitored by file watcher
    └── notes/
        └── *.md                        # Markdown files being watched
```

---

## 7. DATABASE SCHEMA

### file_sync_state Table
```sql
CREATE TABLE file_sync_state (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    file_path TEXT NOT NULL,
    content_hash VARCHAR(64),
    last_modified_at TIMESTAMP WITH TIME ZONE,
    last_embedded_at TIMESTAMP WITH TIME ZONE,  -- This is updated on re-embed
    embedding_model VARCHAR(255),
    vector_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, file_path)
);
```

The `last_embedded_at` column is updated by `embed_and_upsert_note_async()` function.

---

## Summary Table

| Component | Technology | Purpose |
|-----------|-----------|---------|
| VaultWatcher | watchdog 3.0.0 | Detects file system events |
| Observer | watchdog.observers | Monitors /vault directory recursively |
| Debounce | Celery countdown | 30-second delay before checking |
| schedule_embedding_check | Celery task | Verifies content change, extracts note ID |
| embed_note_task | Celery task | Generates embedding, updates database |
| Startup | on_after_configure hook | Starts observer in daemon thread |
| Execution | Async/asyncio | All embedding tasks use async/await |

