# File Watcher Implementation - Complete Documentation

This directory contains comprehensive documentation about the file watcher implementation that monitors the vault directory for external file changes and triggers re-embedding of notes.

## Documentation Files

### 1. FILE_WATCHER_ANALYSIS.md (Main Document)
Comprehensive analysis covering:
- Where the file watcher code is located
- How it detects file changes (watchdog library)
- How it triggers re-embedding (task chain)
- 6 identified issues with root cause analysis
- 6 recommended fixes with code examples
- Database schema and architecture overview

**Read this first for detailed understanding.**

### 2. FILEWATCHER_CODEFLOW.md (Visual Guide)
ASCII diagrams and flow charts showing:
- Startup flow of file watcher
- File modification event flow
- Content check and hash comparison logic
- Re-embedding task chain execution
- Database state changes before/after
- Test expectations vs actual timing
- Detailed timing diagram (0s to 37s+)
- Code locations summary in tasks.py
- Known bugs highlighted

**Read this for visual understanding of the flow.**

### 3. FILE_WATCHER_README.md (This File)
Index and quick navigation guide.

## Quick Answers to Your Questions

### Q1: Where is the file watcher code?
**Answer**: `/home/user/brainda/app/worker/tasks.py` (lines 526-598)

Key components:
- `VaultWatcher` class (lines 527-542) - detects .md file modifications
- `start_file_watcher()` function (lines 544-552) - starts observer
- `setup_periodic_tasks()` hook (lines 593-598) - Celery startup initialization

### Q2: How does it detect file changes?
**Answer**: Uses `watchdog==3.0.0` library

Detection mechanism:
1. `watchdog.observers.Observer` monitors `/vault` directory recursively
2. `VaultWatcher.on_modified()` callback triggered on file system events
3. Filters for `.md` files only (skips directories)
4. Sends filepath to Celery task with 30-second debounce

### Q3: How does it trigger re-embedding?
**Answer**: Multi-stage task chain

Flow:
```
File modification
    ↓
VaultWatcher.on_modified()
    ↓ [30s debounce]
schedule_embedding_check() - verify content change
    ↓
embed_note_task() - generate embedding
    ↓
embed_and_upsert_note_async() - update database
    ↓
file_sync_state.last_embedded_at = NOW()
```

### Q4: Why might it not be working?
**Answer**: 6 identified issues

**Critical Issues:**
1. **Path bug (line 239)**: `replace('/vault/', '')` breaks with nested paths
2. **Debounce timing (line 528)**: 30s hardcoded, test expects immediate check
3. **Thread lifecycle (line 597)**: No verification observer is ready
4. **Error handling (line 242)**: Missing exception types
5. **Frontmatter failure (line 261)**: Silent failure if note_id not found
6. **Container mismatch**: File watcher may run in different container than API

## Key Code Snippets

### VaultWatcher Class (Line 527-542)
Monitors `/vault` directory for `.md` file modifications and queues tasks.

### schedule_embedding_check (Line 235-269)
Verifies file content changed, extracts note ID, queues embedding task.

### embed_note_task (Line 271-301)
Generates embeddings and updates database timestamp.

### embed_and_upsert_note_async (Line 185-227)
Actually updates `file_sync_state.last_embedded_at = NOW()`.

## Database Table

### file_sync_state
```sql
CREATE TABLE file_sync_state (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    file_path TEXT NOT NULL,
    content_hash VARCHAR(64),
    last_modified_at TIMESTAMP WITH TIME ZONE,
    last_embedded_at TIMESTAMP WITH TIME ZONE,  -- UPDATED BY WATCHER
    embedding_model VARCHAR(255),
    vector_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, file_path)
);
```

The `last_embedded_at` column is the key metric being tested.

## Test Details

### Test: stage1.sh:127-137 (external_edit case)
- Edits vault/notes/example.md externally
- Expects `last_embedded_at` to be updated within 180 seconds
- Currently times out because test doesn't account for 30-second debounce

### Actual Timeline
```
0s   - File edited
30s  - schedule_embedding_check starts
35s+ - embed_note_task completes, DB updated
37s+ - Query shows new timestamp
```

### Recommended Test Fix
Add `sleep 35` after file edit to account for debounce delay.

## Architecture Overview

```
Celery Worker Container (vib-worker)
    |
    +-- File Watcher (daemon thread)
    |   |
    |   +-- watchdog Observer
    |   |
    |   +-- VaultWatcher event handler
    |
    +-- Celery Task Queue
        |
        +-- schedule_embedding_check task
        |
        +-- embed_note_task task
        |
        +-- Database updates

Shared Volume (./vault)
    |
    +-- Mounted at /vault in both orchestrator and worker containers
    |
    +-- Contains markdown files for notes
```

## Related Files

### Source Code
- `/home/user/brainda/app/worker/tasks.py` - Main implementation
- `/home/user/brainda/app/api/main.py` - API endpoints (creates notes)
- `/home/user/brainda/app/api/requirements.txt` - Dependencies (watchdog==3.0.0)

### Configuration
- `/home/user/brainda/docker-compose.yml` - Volume mounts
- `/home/user/brainda/.env` - Environment variables

### Tests
- `/home/user/brainda/tests/stage1.sh` - Test case (lines 127-137)

## Dependencies

- `watchdog==3.0.0` - File system event monitoring
- `celery==5.3.4` - Distributed task queue
- `asyncpg==0.29.0` - PostgreSQL async driver
- `qdrant-client==1.6.0` - Vector database client
- `sentence-transformers>=3.0.0` - Embedding model

## Recommended Next Steps

1. **Read FILE_WATCHER_ANALYSIS.md** for comprehensive understanding
2. **Read FILEWATCHER_CODEFLOW.md** for visual flow diagrams
3. **Review the 6 issues** identified in the analysis
4. **Implement fixes** in priority order:
   - Fix #1: Path handling (use pathlib)
   - Fix #2: Debounce configuration
   - Fix #3: Observer startup verification
   - Fix #4: Better error handling
   - Fix #5: Frontmatter logging
   - Fix #6: Test timing adjustment

## Summary

The file watcher is **working conceptually** but has:
- **Design issues** (hardcoded debounce, simple path replace)
- **Test timing issues** (doesn't account for debounce)
- **Error handling gaps** (missing exception types)
- **Lifecycle issues** (no startup verification)

All issues are fixable. See FILE_WATCHER_ANALYSIS.md for detailed remediation steps.

---

**Created**: 2025-11-13
**Location**: /home/user/brainda/
**Files**: 
- FILE_WATCHER_ANALYSIS.md (Comprehensive analysis)
- FILEWATCHER_CODEFLOW.md (Visual flow diagrams)
- FILE_WATCHER_README.md (This index)
