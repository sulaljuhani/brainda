# File Watcher Code Flow Diagram

## Startup Flow

```
Celery Worker Startup
    |
    v
@celery_app.on_after_configure.connect hook
    |
    v
setup_periodic_tasks() called
    |
    +---> threading.Thread(target=start_file_watcher, daemon=True)
    |
    v
start_file_watcher() function
    |
    +---> path = "/vault"
    |
    +---> VaultWatcher() instantiated (debounce_seconds=30)
    |
    +---> Observer() instantiated
    |
    +---> observer.schedule(event_handler, path, recursive=True)
    |
    +---> observer.start()
    |
    v
File Watcher Running (in background thread)
    |
    Observer listens for /vault directory changes
```

---

## File Modification Event Flow

```
External File Modification (user edits vault/notes/example.md)
    |
    v [OS notifies watchdog]
    |
VaultWatcher.on_modified(event)
    |
    +---> Check: event.is_directory? NO, proceed
    |
    +---> Check: event.src_path.endswith('.md')? YES, proceed
    |
    +---> filepath = event.src_path  (e.g., "/vault/notes/example.md")
    |
    +---> self.pending_changes[filepath] = time.time()
    |
    v
schedule_embedding_check.apply_async(
    args=[filepath],
    countdown=30      <-- 30 SECOND DELAY
)
    |
    [Task queued in Redis/Celery]
    |
    v
*** WAIT 30 SECONDS ***
    |
    v
schedule_embedding_check(filepath) task executes
```

---

## Content Check and Hash Comparison Flow

```
schedule_embedding_check(filepath) executes
    |
    v
relative_path = filepath.replace('/vault/', '')
    |
    +---> Example: "/vault/notes/example.md" -> "notes/example.md"
    |
    v
Try: with open(filepath, 'r') as f:
         content = f.read()
    |
    +---> Success: proceed
    +---> FileNotFoundError: log warning and return
    
    v
content_hash = hashlib.sha256(content.encode()).hexdigest()
    |
    +---> Calculate SHA256 of current file content
    |
    v
conn = await _connect_db()
    |
    v
SELECT content_hash, last_embedded_at 
FROM file_sync_state 
WHERE file_path = 'notes/example.md'
    |
    v
Compare hashes:
    |
    +---> If no record exists:       proceed to embed
    |
    +---> If content_hash == new hash: NO CHANGE, return (nothing to do)
    |
    +---> If content_hash != new hash: CHANGE DETECTED, proceed
    |
    v
note_id = extract_note_id_from_frontmatter(content)
    |
    +---> Parse YAML frontmatter between "---" markers
    |
    +---> Extract "id: <uuid>" field
    |
    v
if note_id:
    |
    +---> SUCCESS: embed_note_task.delay(str(note_id))
    |
    v [Task queued immediately]
else:
    |
    +---> FAILURE: log warning "no_note_id_in_frontmatter"
    |
    v [Return, no re-embedding happens]
```

---

## Re-Embedding Task Chain Flow

```
embed_note_task(note_id_str) executes
    |
    v
note_id = uuid.UUID(note_id_str)
    |
    v
conn = await _connect_db()
    |
    v
SELECT * FROM notes WHERE id = note_id
    |
    +---> If found: proceed
    +---> If not found: log warning and return
    |
    v
embed_and_upsert_note_async(
    note_id, title, body, tags, md_path, user_id
)
    |
    v
text = f"{title}\n\n{body}"
    |
    v
embedding = await embedding_service.embed(text)
    |
    +---> Calls Sentence Transformers model
    +---> Generates vector embedding (384 dimensions)
    |
    v
client = QdrantClient(url=QDRANT_URL)
    |
    v
client.upsert(
    collection_name="knowledge_base",
    points=[{
        "id": str(note_id),
        "vector": embedding,
        "payload": {
            "embedding_model": model_name,
            "content_type": "note",
            ...
        }
    }]
)
    |
    +---> Store or update vector in Qdrant
    |
    v
conn = await _connect_db()
    |
    v
INSERT INTO file_sync_state (
    user_id, 
    file_path, 
    content_hash, 
    last_modified_at, 
    last_embedded_at = NOW(),  <-- **KEY UPDATE**
    embedding_model, 
    vector_id
)
ON CONFLICT (user_id, file_path) DO UPDATE
SET content_hash = ...,
    last_embedded_at = NOW(),  <-- **KEY UPDATE**
    vector_id = ...,
    updated_at = NOW()
    |
    v
UPDATE notes
SET updated_at = NOW()
WHERE id = note_id
    |
    v
Log: embed_note_task_success
    |
    v
Return (Task Complete)
```

---

## Database State Changes

### Before External Edit:
```
file_sync_state table:
┌─────────────────────────────────────────────────────────────┐
│ user_id │ file_path           │ last_embedded_at            │
├─────────────────────────────────────────────────────────────┤
│ user-1  │ notes/example.md    │ 2025-11-13 10:00:00+00      │
└─────────────────────────────────────────────────────────────┘
```

### External File Edit (append text to notes/example.md)
```
[File system event] -> watchdog triggers on_modified()
```

### After Re-Embedding (at time ~10:00:30 to 10:00:35):
```
file_sync_state table:
┌─────────────────────────────────────────────────────────────┐
│ user_id │ file_path           │ last_embedded_at            │
├─────────────────────────────────────────────────────────────┤
│ user-1  │ notes/example.md    │ 2025-11-13 10:00:33+00      │ <-- UPDATED
└─────────────────────────────────────────────────────────────┘
```

---

## Test Expectation (stage1.sh:127-137)

```
before=$(psql_query "SELECT extract(epoch FROM last_embedded_at) ...")
    |
    v [Snapshot the current timestamp]
    | before = 1694526000.0

echo "\nUpdated $(date)" >> "$file"
    |
    v [Externally modify the file]
    |
wait_for "... WHERE file_path = ... 'AND extract(...) > $before" 180 "..."
    |
    v [Poll database for 180 seconds looking for timestamp > before]
    |
    + PROBLEM: Polling starts immediately
    + But file watcher waits 30 seconds before even checking
    + So database won't update until 30s+
    |
    v [After re-embedding completes]
    |
after=$(psql_query "SELECT extract(epoch FROM last_embedded_at) ...")
    |
    v [Compare timestamps]
    |
assert_greater_than "$after" "$before"
```

---

## Timing Diagram

```
Timeline (seconds):

0s   ├─ File edited: echo "..." >> vault/notes/example.md
     │
     ├─ watchdog detects change immediately
     │
     ├─ VaultWatcher.on_modified() called
     │
     ├─ schedule_embedding_check.apply_async(..., countdown=30) queued
     │
30s  │
     ├─ schedule_embedding_check task STARTS executing
     │
     ├─ Reads file
     │
     ├─ Calculates hash
     │
     ├─ Queries database
     │
     ├─ Extracts note_id
     │
     ├─ embed_note_task.delay() queued
     │
     ├─ embed_note_task STARTS executing
     │
     ├─ Generates embedding (2-5 seconds)
     │
35s  │
     ├─ Updates database (1-2 seconds)
     │
     │   INSERT/UPDATE file_sync_state
     │   SET last_embedded_at = NOW()  <-- **DATABASE UPDATED**
     │
37s  │
     ├─ Task completes
     │
     ├─ next query of file_sync_state will show new timestamp
     │
     v
```

---

## Code Locations Summary

```python
# File: /home/user/brainda/app/worker/tasks.py

Lines 1-20      : Imports (watchdog on line 20-21)
Lines 44-61     : Celery app configuration
Lines 100-135   : Utility functions
Lines 138-150   : extract_note_id_from_frontmatter()
Lines 185-227   : embed_and_upsert_note_async() <-- Updates last_embedded_at
Lines 230-234   : health_check task
Lines 235-269   : schedule_embedding_check() <-- Main logic (LINE 239 BUG)
Lines 271-301   : embed_note_task() <-- Queues re-embedding
Lines 304-434   : process_document_ingestion() 
Lines 471-523   : cleanup_old_data()
Lines 526-542   : VaultWatcher class <-- File change detector
Lines 544-552   : start_file_watcher() <-- Starts observer
Lines 593-598   : setup_periodic_tasks() <-- Startup hook
Lines 601-964   : Google Calendar sync tasks
```

---

## Known Bugs in Code

### Bug #1: Line 239 - Path String Replace
```python
relative_path = filepath.replace('/vault/', '')
```
- Fragile: breaks if "/vault/" appears multiple times
- Should use: `str(Path(filepath).relative_to('/vault'))`

### Bug #2: Line 528 - Hardcoded Debounce
```python
def __init__(self, debounce_seconds=30):
```
- Not configurable for testing
- Should read from environment: `os.getenv('FILE_WATCHER_DEBOUNCE', '30')`

### Bug #3: Line 597 - No Observer Verification
```python
watcher_thread.start()
# Missing: time.sleep(0.5) and observer.is_alive() check
```

