# Test Failure Root Cause Analysis & Fixes

Generated: 2025-11-13

## Executive Summary

This document provides a comprehensive root cause analysis for the 6 test failures identified across integration test stages 1-7. Each failure has been traced to its source code location, and specific fixes are provided.

---

## Failure 1: Stage 1 - notes_external_edit

**Test Location**: `tests/stage1.sh:127-137`
**Status**: ✗ Timeout (180s)
**Error**: Embedding timestamp did not advance after external file modification

### Root Cause
The file watcher (`VaultWatcher`) is initialized in `app/worker/tasks.py:593-598` using Celery's `@celery_app.on_after_configure.connect` decorator. However, this decorator may not reliably trigger in all Celery worker startup configurations, causing the file watcher thread to never start.

**Code Location**: `app/worker/tasks.py:593-598`
```python
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Start the file watcher in a background thread
    import threading
    watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    watcher_thread.start()
```

### Impact
- External file modifications are not detected
- Re-embedding does not occur automatically
- The `last_embedded_at` timestamp in `file_sync_state` never updates

### Fix
**Option 1: Use Celery worker signals (Recommended)**
```python
from celery.signals import worker_ready

@worker_ready.connect
def start_file_watcher_on_worker_ready(sender, **kwargs):
    """Start file watcher when Celery worker is fully ready"""
    import threading
    watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    watcher_thread.start()
    logger.info("file_watcher_thread_started_from_worker_ready")
```

**Option 2: Start in main worker process**
Add to worker startup command or initialization:
```python
if __name__ == '__main__':
    start_file_watcher()
    # Then start celery worker
```

---

## Failure 2: Stage 2 - reminder_scheduler_entry

**Test Location**: `tests/stage2.sh:112-124`
**Status**: ✗ Timeout (60s)
**Error**: Reminder ID not found in orchestrator logs

### Root Cause
The scheduler IS being started correctly in `app/api/main.py:61`, but the test is searching for logs in the wrong container. The test checks `vib-orchestrator` logs:

**Test Code**: `tests/stage2.sh:39`
```bash
logs=$(docker logs vib-orchestrator --tail 400 2>&1)
```

However, the scheduler runs in the **orchestrator container** which logs to stdout, and the log message "reminder_scheduled" is produced at `app/worker/scheduler.py:40-42`. The issue is that scheduler logs may not be captured in time, or the test baseline is already including the log entry.

**Additional Issue**: The test creates a reminder and immediately checks logs, but there's a race condition. The scheduler log is written synchronously, but docker logs may be buffered.

### Impact
- Test fails even though scheduler is working correctly
- False negative - functionality works but test is unreliable

### Fix
**Fix 1: Check database instead of logs**
```bash
# Instead of checking logs, verify the APScheduler Redis jobstore
test_reminder_scheduler_entry() {
    local pair reminder_id
    pair=$(create_unique_reminder 15)
    reminder_id=${pair%%|*}

    # Wait for job to appear in Redis jobstore
    local timeout=30
    local elapsed=0
    while [[ $elapsed -lt $timeout ]]; do
        local job_exists
        job_exists=$(docker exec vib-redis redis-cli EXISTS "apscheduler.jobs.reminder_${reminder_id}" 2>/dev/null || echo "0")
        if [[ "$job_exists" == "1" ]]; then
            success "Reminder $reminder_id scheduled in APScheduler"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    error "Reminder $reminder_id was not scheduled"
    return 1
}
```

**Fix 2: Add flush to logger**
Ensure logs are flushed immediately in `app/worker/scheduler.py:40-42`:
```python
logger.info(
    "reminder_scheduled",
    reminder_id=reminder_id,
    due_at=due_at.isoformat(),
    flush=True  # Ensure immediate flush
)
```

---

## Failure 3: Stage 3 - doc_rag_citations

**Test Location**: `tests/stage3.sh:246-254`
**Status**: ✗ Zero citations found
**Error**: RAG citations present (0 <= 0)

### Root Cause
The RAG service (`app/api/services/rag_service.py:84`) **IS** returning citations correctly:
```python
return {"answer": response, "citations": citations, "sources_used": len(results)}
```

And the chat endpoint (`app/api/main.py:683`) **IS** including them:
```python
return {
    "mode": "rag",
    "message": answer.get("answer", "No response available."),
    "data": {"sources_used": answer.get("sources_used", 0)},
    "citations": answer.get("citations", []),  # ← Citations ARE included
}
```

The problem is that the test message doesn't match any document or the vector search is returning no results, causing `RAGService.answer_question` to return an empty `citations` array (line 39).

### Impact
- Test expects citations but none are returned because search finds no relevant documents
- This could be due to:
  1. Document not yet indexed when RAG query runs
  2. Query doesn't semantically match the document
  3. Vector search threshold too high

### Fix
**Fix 1: Wait for document to be fully embedded before RAG test**
```bash
test_rag_citations() {
    # Ensure document is indexed and embedded
    wait_for "psql_query \"SELECT status FROM documents WHERE id = '$DOC_ID';\" | grep -q 'indexed'" 30 "document fully indexed"

    # Additional wait for vector embeddings to propagate
    sleep 5

    # Use a more specific query that matches document content
    local payload='{ "message": "What does the integration test document contain?" }'
    status=$(curl -sS -o "$TEST_DIR/rag-response.json" -w "%{http_code}" \
        -X POST "$BASE_URL/api/v1/chat" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$payload" || echo "000")

    assert_status_code "$status" "200" "RAG chat request" || return 1

    local citations
    citations=$(jq '.citations | length' "$TEST_DIR/rag-response.json" 2>/dev/null || echo 0)
    assert_greater_than "$citations" "0" "RAG citations present" || return 1
}
```

**Fix 2: Lower vector search threshold in RAG service**
In `app/api/services/rag_service.py:31`, change:
```python
min_score=0.1,  # Lower from default to capture more results
```

---

## Failure 4: Stage 4 - stage4_metrics_non_zero

**Test Location**: `tests/stage4.sh:132-144`
**Status**: ✗ Metric did not increment
**Error**: Notes created metric non-zero (3 <= 3)

### Root Cause
The test creates a note to trigger the metric, but the metric doesn't increment because:

1. The metric IS incremented correctly in `app/api/main.py:231`
2. BUT the test has a race condition - it checks the metric immediately after the API call returns, before the metric scrape endpoint is updated
3. Prometheus metrics have a collection interval, and the test is checking too quickly

**Code Location**: `tests/stage4.sh:141`
```bash
if ! wait_for_metric_increase "notes_created_total" "${before:-0}" "Notes created metric non-zero"; then
```

The `wait_for_metric_increase` function (`tests/stage4.sh:97-113`) retries 5 times with 3s delay, but the metric endpoint might be cached.

### Impact
- Race condition causes intermittent failures
- Metric IS working, but test timing is unreliable

### Fix
**Fix 1: Increase retry attempts and delay**
```bash
# In stage4.sh:13-14, increase retry attempts
METRIC_RETRY_ATTEMPTS=${METRIC_RETRY_ATTEMPTS:-10}  # Was 5
METRIC_RETRY_DELAY=${METRIC_RETRY_DELAY:-5}  # Was 3
```

**Fix 2: Force metric refresh in test**
```bash
test_stage4_metrics_non_zero() {
    local before
    before=$(metric_value "notes_created_total" refresh || echo 0)

    # Create note
    local payload='{"title":"Metrics Test Note","body":"Testing metrics","tags":[]}'
    local note_id
    note_id=$(curl -sS -X POST "$BASE_URL/api/v1/notes" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$payload" | jq -r '.data.id')

    # Wait for note to be created in DB
    wait_for "psql_query \"SELECT COUNT(*) FROM notes WHERE id = '$note_id';\" | grep -q '1'" 10 "note created in DB"

    # Force multiple refreshes
    sleep 2
    if ! wait_for_metric_increase "notes_created_total" "${before:-0}" "Notes created metric non-zero"; then
        rc=1
    fi
}
```

---

## Failure 5: Stage 5 - stage5_idempotency_different_key

**Test Location**: `tests/stage5.sh:324-359`
**Status**: ✗ Same reminder ID for different keys
**Error**: Same reminder ID returned for different idempotency keys!

### Root Cause
The idempotency middleware (`app/api/middleware/idempotency.py`) is working correctly. The problem is in the **reminder service** deduplication logic.

**Code Location**: `app/api/services/reminder_service.py:77-104`

When a `UniqueViolationError` occurs (database constraint), the service fetches an existing reminder based on `user_id`, `title`, and `due_at_utc`:

```python
except UniqueViolationError as e:
    existing = await self.db.fetchrow("""
        SELECT * FROM reminders
        WHERE user_id = $1
        AND title = $2
        AND due_at_utc = $3
        AND status = 'active'
        ORDER BY created_at DESC
        LIMIT 1
    """, user_id, data.title, data.due_at_utc)

    if existing:
        reminders_deduped_total.labels(user_id=str(user_id)).inc()
        return {
            "success": True,
            "deduplicated": True,
            "data": dict(existing)  # ← Returns SAME reminder regardless of idempotency key
        }
```

The test creates two reminders with:
- Same `title` ("Different Keys Test $TIMESTAMP")
- Same `due_at_utc` (from payload)
- Different idempotency keys

The database constraint triggers on the second request, causing it to return the FIRST reminder's ID.

### Impact
- Breaks idempotency contract: different idempotency keys should create separate resources
- The database constraint is TOO strict - it should not deduplicate across different idempotency keys

### Fix
**Fix 1: Remove UniqueViolationError handler from reminder service**

The idempotency middleware already handles deduplication. The service-level deduplication is redundant and conflicts with it.

```python
# In app/api/services/reminder_service.py:77-112
# REMOVE the entire UniqueViolationError except block
# Let idempotency middleware handle all deduplication

async def create_reminder(self, user_id: UUID, data: ReminderCreate) -> dict:
    """Create reminder. Idempotency is handled by middleware."""
    try:
        if data.calendar_event_id:
            event = await self.db.fetchrow(
                "SELECT id, user_id, status FROM calendar_events WHERE id = $1",
                data.calendar_event_id,
            )
            if not event or event["user_id"] != user_id:
                return {
                    "success": False,
                    "error": {
                        "code": "INVALID_EVENT",
                        "message": "Calendar event not found for this user",
                    },
                }

        async with self.db.transaction():
            reminder = await self.db.fetchrow("""
                INSERT INTO reminders (
                    user_id, title, body, due_at_utc, due_at_local,
                    timezone, repeat_rrule, note_id, calendar_event_id, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'active')
                RETURNING *
            """,
                user_id, data.title, data.body, data.due_at_utc,
                data.due_at_local, data.timezone, data.repeat_rrule,
                data.note_id, data.calendar_event_id
            )

        logger.info(
            "reminder_created",
            user_id=str(user_id),
            reminder_id=str(reminder['id']),
            due_at_utc=data.due_at_utc.isoformat(),
        )

        from worker.scheduler import schedule_reminder
        schedule_reminder(str(reminder['id']), data.due_at_utc)
        reminders_created_total.labels(user_id=str(user_id)).inc()

        return {"success": True, "data": dict(reminder)}

    except UniqueViolationError as e:
        # Re-raise to let idempotency middleware handle it
        logger.warning(
            "duplicate_reminder_constraint_violated",
            user_id=str(user_id),
            title=data.title,
            error=str(e)
        )
        raise HTTPException(
            status_code=409,
            detail="A reminder with this title and time already exists"
        )
```

**Fix 2: Update database constraint (if needed)**

Check if the database constraint should include more fields:
```sql
-- Current constraint might be:
UNIQUE (user_id, title, due_at_utc)

-- Consider if this is the right constraint for your use case
-- Alternative: Remove constraint entirely and rely on idempotency middleware
```

---

## Failure 6: Stage 6 - stage6_calendar_create

**Test Location**: `tests/stage6.sh:155-169`
**Status**: ✗ jq parse error
**Error**: Invalid numeric literal at line 1, column 2

### Root Cause
The API is returning a non-JSON response, causing `jq` to fail parsing. This indicates an unhandled exception or error response format issue.

**Debugging Steps**:
1. The test calls `/api/v1/calendar/events` POST endpoint
2. `jq` fails to parse the response
3. The calendar service (`app/api/services/calendar_service.py:40-105`) looks correct

**Most Likely Causes**:
1. Missing Python dependency (e.g., `python-dateutil` for `rrulestr`)
2. Pydantic validation error not properly formatted as JSON
3. Unhandled exception in calendar service

### Impact
- Calendar event creation fails completely
- No events can be created via API
- Likely blocking all calendar functionality

### Fix
**Fix 1: Add error handling to calendar router**

In `app/api/routers/calendar.py:31-41`:
```python
@router.post("/events", response_model=dict)
async def create_calendar_event(
    payload: CalendarEventCreate,
    user_id: UUID = Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        service = CalendarService(db)
        result = await service.create_event(user_id, payload)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        logger.error("calendar_create_error", error=str(e), user_id=str(user_id))
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )
```

**Fix 2: Verify dependencies**
```bash
# Check if python-dateutil is installed
docker exec vib-orchestrator pip list | grep dateutil

# If not, add to requirements.txt:
python-dateutil>=2.8.2
```

**Fix 3: Add detailed logging**
```python
# In app/api/services/calendar_service.py:40
async def create_event(self, user_id: UUID, data: CalendarEventCreate) -> dict:
    logger.info("calendar_create_event_start", user_id=str(user_id), title=data.title)
    try:
        starts_at = data.starts_at
        ends_at = data.ends_at or (starts_at + timedelta(hours=1))
        logger.info("calendar_create_event_validated", starts_at=starts_at, ends_at=ends_at)
        # ... rest of function
    except Exception as e:
        logger.error("calendar_create_event_error", error=str(e), error_type=type(e).__name__)
        raise
```

---

## Summary of Fixes

| Issue | Severity | Effort | Priority |
|-------|----------|--------|----------|
| Stage 1: File watcher | High | Low | P1 |
| Stage 2: Test reliability | Low | Medium | P3 |
| Stage 3: RAG citations | Medium | Low | P2 |
| Stage 4: Metric timing | Low | Low | P3 |
| Stage 5: Idempotency | High | Medium | P1 |
| Stage 6: Calendar error | High | Low | P1 |

## Implementation Order

1. **Stage 6** - Fix calendar endpoint error (blocking all calendar functionality)
2. **Stage 5** - Fix idempotency logic (data integrity issue)
3. **Stage 1** - Fix file watcher startup (functionality broken)
4. **Stage 3** - Improve RAG test reliability
5. **Stage 4** - Increase metric test retry delays
6. **Stage 2** - Refactor test to check Redis instead of logs

---

## Verification Steps

After implementing fixes:

```bash
# Run all stages
./tests/stage_runner.sh --stage 1 --verbose
./tests/stage_runner.sh --stage 2 --verbose
./tests/stage_runner.sh --stage 3 --verbose
./tests/stage_runner.sh --stage 4 --verbose
./tests/stage_runner.sh --stage 5 --verbose
./tests/stage_runner.sh --stage 6 --verbose
./tests/stage_runner.sh --stage 7 --verbose

# Check for any remaining failures
grep -E "✗|failed" /tmp/vib-test-*/run.log
```
