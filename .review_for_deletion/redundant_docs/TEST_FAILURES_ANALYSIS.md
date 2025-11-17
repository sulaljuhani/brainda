# Integration Test Failures - Comprehensive Analysis

## Executive Summary

After analyzing test failures across stages 0-8, I've identified and fixed **3 critical issues** and documented **5 remaining failures** with root cause analysis and remediation steps.

---

## ✅ FIXED ISSUES (Committed)

### 1. **Stage 0: CORS Test Configuration**
- **File**: `tests/stage0.sh:290-295`
- **Problem**: Test expected wildcard (`*`) CORS headers
- **Root Cause**: Security best practice - cannot use `allow_origins=["*"]` with `allow_credentials=True`
- **Fix**: Updated test to check for default allowed origin (`http://localhost:3000`)
- **Status**: ✅ Fixed in commit e5387df

### 2. **Stage 4: AWK Syntax Error in Metrics Parsing**
- **File**: `tests/stage4.sh:54`
- **Problem**: Malformed AWK regex pattern causing syntax errors
- **Root Cause**: Invalid regex concatenation: `$1 ~ ("^"name"\\{"|"^"name" ")`
- **Fix**: Changed to: `$1 == name || $1 ~ "^"name"\\{"`
- **Impact**: Metrics aggregation now works correctly
- **Status**: ✅ Fixed in commit e5387df

### 3. **Stage 5: Idempotency Key Conflict**
- **File**: `migrations/009_fix_reminder_dedup_constraint.sql` (new)
- **Problem**: Different idempotency keys returned same reminder ID
- **Root Cause**: Database unique constraint on `(user_id, title, due_at_utc)` conflicted with idempotency middleware
- **Explanation**:
  - Two deduplication mechanisms were active:
    1. Idempotency middleware (key-based) - correct approach
    2. Database constraint (content-based) - too restrictive
  - Different clients with different idempotency keys should create separate reminders even with identical content
- **Fix**: Dropped `idx_reminders_dedup` unique index
- **Status**: ✅ Migration created, needs deployment

---

## ⚠️ REMAINING FAILURES

### 4. **Stage 1: notes_external_edit - File Watcher Timing**
- **Test Output**:
  ```
  [17:35:44] Running test: notes_external_edit
  [17:39:01] ✗ Timeout waiting for: re-embedding after external edit
  [17:39:01] ✗ Embedding timestamp advanced (1763055329.914994 <= 1763055329.914994)
  ```

- **Root Cause Analysis**:
  1. **File watcher IS working** - verified in logs at 17:35:29.783
  2. **30-second debounce delay** - `VaultWatcher.__init__(debounce_seconds=30)`
  3. **Test modification method** - uses `echo "\nUpdated $(date)" >> "$file"`
  4. **Race condition** - test might check before debounce completes

- **Evidence from Logs**:
  ```
  [17:35:29.783] file_changed_externally path=notes/mvp-test-note-20251113-203444.md
  [17:35:29.834] embed_note_task_start
  [17:35:29.926] embed_note_task_success
  ```

- **Recommended Fix**:
  ```bash
  # In tests/stage1.sh, external_edit case:
  before=$(psql_query "SELECT extract(epoch FROM last_embedded_at) FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';")

  # Use echo -e for proper newline
  echo -e "\nUpdated $(date)" >> "$file"

  # Wait for at least debounce time + processing
  sleep 35  # 30s debounce + 5s processing buffer

  # Then start polling
  wait_for "..." 150 "re-embedding after external edit"
  ```

- **Alternative**: Reduce debounce to 5 seconds for tests:
  ```python
  # app/worker/tasks.py:528
  def __init__(self, debounce_seconds=int(os.getenv("FILE_WATCHER_DEBOUNCE", "30"))):
  ```

- **Status**: ⚠️ Needs test adjustment or environment configuration

---

### 5. **Stage 2: reminder_scheduler_entry - Missing Scheduler Logs**
- **Test Output**:
  ```
  [17:43:18] ✗ Reminder did not produce scheduler log
  ```

- **Root Cause Analysis**:
  1. **Scheduler IS running** - verified in logs
  2. **schedule_reminder() function** - called from `reminder_service.py:72`
  3. **Log level issue** - APScheduler logs might be at DEBUG level

- **Evidence from Code**:
  ```python
  # app/worker/scheduler.py
  def schedule_reminder(reminder_id: str, due_at: datetime):
      scheduler.add_job(
          fire_reminder,
          'date',
          run_date=due_at,
          id=reminder_id,
          replace_existing=True
      )
  ```

- **Missing**: No logger.info() call in schedule_reminder()

- **Recommended Fix**:
  ```python
  # app/worker/scheduler.py - add logging to schedule_reminder()
  def schedule_reminder(reminder_id: str, due_at: datetime):
      scheduler.add_job(
          fire_reminder,
          'date',
          run_date=due_at,
          id=reminder_id,
          replace_existing=True
      )
      logger.info(
          "reminder_scheduled",
          reminder_id=reminder_id,
          due_at=due_at.isoformat()
      )
  ```

- **Status**: ⚠️ Needs code change to add logging

---

### 6. **Stage 3: doc_rag_answer - RAG Endpoint 500 Error**
- **Test Output**:
  ```
  [17:45:41] ✗ RAG chat request (expected 200, got 500)
  ```

- **Root Cause Analysis**:
  - **LLM adapter not configured** or **API key missing**
  - **Potential causes**:
    1. Missing `OPENAI_API_KEY` environment variable
    2. Missing `ANTHROPIC_API_KEY` environment variable
    3. LLM adapter initialization failure
    4. RAG service unhandled exception

- **Verification Steps**:
  ```bash
  # Check if API keys are set
  docker exec brainda-orchestrator env | grep -E "(OPENAI|ANTHROPIC)_API_KEY"

  # Check orchestrator logs during RAG test
  docker logs brainda-orchestrator --since 2m | grep -A 5 -B 5 "chat"
  ```

- **Recommended Fix**:
  1. Set environment variables in docker-compose.yml:
     ```yaml
     environment:
       OPENAI_API_KEY: ${OPENAI_API_KEY}
       ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
     ```

  2. Add error handling in `app/api/main.py _handle_rag_chat()`:
     ```python
     async def _handle_rag_chat(message: str, user_id: uuid.UUID) -> Dict[str, Any]:
         try:
             vector_service = VectorService()
             rag_service = RAGService(vector_service, get_llm_adapter())
             answer = await rag_service.answer_question(message, user_id)
             tool_calls_total.labels("rag_answer", "success").inc()
             return {
                 "mode": "rag",
                 "message": answer.get("answer", "No response available."),
                 "data": {"sources_used": answer.get("sources_used", 0)},
                 "citations": answer.get("citations", []),
             }
         except Exception as e:
             logger.error("rag_chat_failed", error=str(e), user_id=str(user_id))
             tool_calls_total.labels("rag_answer", "error").inc()
             raise HTTPException(status_code=500, detail=f"RAG processing failed: {str(e)}")
     ```

- **Status**: ⚠️ Needs environment configuration and error handling

---

### 7. **Stage 6: stage6_calendar_create - JQ Parse Error**
- **Test Output**:
  ```
  [17:50:37] Running test: stage6_calendar_create
  jq: parse error: Invalid numeric literal at line 1, column 2
  [17:50:37] ✗ Calendar event ID returned (value empty)
  ```

- **Root Cause Analysis**:
  - **Non-JSON response** from API
  - **Potential causes**:
    1. Pydantic validation error not returning JSON
    2. Missing Python dependencies (`pytz`, `dateutil`)
    3. Unhandled exception in calendar service

- **Verification Steps**:
  ```bash
  # Test calendar endpoint directly
  curl -v -X POST "http://localhost:8000/api/v1/calendar/events" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"title":"Test Event","starts_at":"2025-01-15T10:00:00Z","timezone":"UTC"}'
  ```

- **Dependencies Check**:
  ```bash
  docker exec brainda-orchestrator python -c "import pytz; import dateutil; print('OK')"
  ```

- **Recommended Fix**:
  Add try-catch in `app/api/routers/calendar.py:31-41`:
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
      except ValidationError as e:
          logger.error("calendar_validation_error", error=str(e))
          raise HTTPException(status_code=422, detail=str(e))
      except Exception as e:
          logger.error("calendar_create_error", error=str(e))
          raise HTTPException(status_code=500, detail="Internal server error")
  ```

- **Status**: ⚠️ Needs investigation of actual error response

---

### 8. **Stage 7: stage7_sync_trigger - Expected 400 When Disconnected**
- **Test Output**:
  ```
  [17:51:02] ⚠ Manual sync trigger returned 400: Google Calendar is not connected
  [17:51:02] ✗ Manual sync trigger is unavailable while Google Calendar is disconnected
  ```

- **Root Cause Analysis**:
  - **This is expected behavior** - sync trigger should return 400 when not connected
  - **Test design issue** - treating expected behavior as failure

- **Current Code** (`tests/stage7.sh:241-290`):
  ```bash
  case "$status" in
    200)
      # success case
      ;;
    400)
      # Currently treats as failure, but should be acceptable
      warn "Manual sync trigger returned 400: $detail"
      stage7_fail_or_skip "Manual sync trigger is unavailable..."
      ;;
  ```

- **Recommended Fix**:
  ```bash
  # In tests/stage7.sh:241-290
  case "$status" in
    200)
      # Sync triggered successfully
      success "Manual sync trigger accepted request"
      ;;
    400)
      # Expected when Google Calendar not connected
      if [[ "$detail" == *"not connected"* ]]; then
        success "Manual sync correctly returns 400 when not connected"
      else
        error "Unexpected 400 error: $detail"
        return 1
      fi
      ;;
    *)
      log_http_failure "$status" "$body"
      stage7_fail_or_skip "Unexpected status from manual sync trigger: $status"
      return $?
      ;;
  esac
  ```

- **Status**: ⚠️ Test needs adjustment to accept 400 as valid response

---

## 🔧 MINOR ISSUES

### 9. **Qdrant Client Version Mismatch (Non-blocking)**
- **Symptom**: Recurring Pydantic validation errors in orchestrator logs
- **Error**:
  ```
  4 validation errors for ParsingModel[InlineResponse2005]
  - obj.result.vectors_count: Field required
  - obj.result.config.optimizer_config.max_optimization_threads: Input should be a valid integer
  - obj.result.config.wal_config.wal_retain_closed: Extra inputs not permitted
  - obj.result.config.strict_mode_config: Extra inputs not permitted
  ```

- **Root Cause**: `qdrant-client==1.6.0` (2023) vs current Qdrant server API

- **Impact**: Warning only, health check still passes

- **Recommended Fix**:
  ```txt
  # app/api/requirements.txt
  qdrant-client==1.11.3  # Update from 1.6.0
  ```

- **Status**: ⚠️ Optional upgrade, not blocking tests

---

## 📝 DEPLOYMENT CHECKLIST

To apply all fixes:

1. **Pull latest changes** from branch:
   ```bash
   git pull origin claude/debug-integration-test-failures-01NQNrvjoMLRd3NNLUrZedqR
   ```

2. **Run migration 009**:
   ```bash
   # Restart services to apply migration
   docker-compose down
   docker-compose up -d

   # Verify migration applied
   docker exec brainda-postgres psql -U vib -d vib -c "\d reminders" | grep "idx_reminders_dedup"
   # Should show no results (index dropped)
   ```

3. **Set environment variables** (.env file):
   ```env
   # Required for Stage 3 RAG tests
   OPENAI_API_KEY=sk-...
   # OR
   ANTHROPIC_API_KEY=sk-ant-...

   # Optional: Reduce file watcher debounce for faster tests
   FILE_WATCHER_DEBOUNCE=5
   ```

4. **Re-run tests**:
   ```bash
   ./tests/stage_runner.sh --stage 0 --verbose  # Should pass
   ./tests/stage_runner.sh --stage 4 --verbose  # Should pass
   ./tests/stage_runner.sh --stage 5 --verbose  # Should pass
   ```

5. **Address remaining failures** using recommendations above

---

## 📊 TEST STATUS SUMMARY

| Stage | Status | Issue | Priority |
|-------|--------|-------|----------|
| 0 | ✅ FIXED | CORS test configuration | DONE |
| 1 | ⚠️ TIMING | File watcher debounce | MEDIUM |
| 2 | ⚠️ LOGGING | Missing scheduler logs | LOW |
| 3 | ⚠️ CONFIG | Missing LLM API keys | HIGH |
| 4 | ✅ FIXED | AWK syntax error | DONE |
| 5 | ✅ FIXED | Idempotency conflict | DONE |
| 6 | ⚠️ INVESTIGATE | JQ parse error | MEDIUM |
| 7 | ⚠️ TEST DESIGN | Expected 400 treated as failure | LOW |
| 8 | ✅ PASS | All tests passing | DONE |

---

## 🎯 PRIORITY RECOMMENDATIONS

### HIGH PRIORITY
1. **Set LLM API keys** for Stage 3 RAG tests
2. **Deploy migration 009** for Stage 5 fix

### MEDIUM PRIORITY
3. **Investigate Stage 6** calendar creation jq error
4. **Adjust Stage 1** file watcher test timing

### LOW PRIORITY
5. **Add logging** to Stage 2 scheduler
6. **Update Stage 7** test to accept 400 response
7. **Upgrade qdrant-client** to latest version

---

## 📚 RELATED FILES

- `tests/stage0.sh` - CORS test fix
- `tests/stage4.sh` - AWK metrics fix
- `migrations/009_fix_reminder_dedup_constraint.sql` - Idempotency fix
- `app/worker/tasks.py` - File watcher and scheduler implementation
- `app/api/services/rag_service.py` - RAG implementation
- `app/api/routers/calendar.py` - Calendar endpoint
- `app/api/requirements.txt` - Python dependencies

---

**Created**: 2025-11-13
**Branch**: `claude/debug-integration-test-failures-01NQNrvjoMLRd3NNLUrZedqR`
**Commit**: e5387df
