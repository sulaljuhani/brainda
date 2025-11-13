# Stage 3 Test Script Review (`tests/stage3.sh`)

## Pre-review Metadata
- **Script purpose:** Exercises Stage 3 ingestion → chunking → vector search → RAG behaviors for the primary PDF knowledge base flow.
- **Entry points:** `run_stage3` iterates over ~30 logical checks implemented inside the `documents_check` case statement.
- **External dependencies:** Postgres (`psql_query`), Qdrant on `localhost:6333`, the `/api/v1/ingest`, `/api/v1/jobs`, `/api/v1/search`, `/api/v1/chat`, `/api/v1/documents` HTTP endpoints, Prometheus metrics, the helper functions from `tests/common.sh`, and a writable `$TEST_DIR` for fixtures.

---

## Phase 2 – Testing Methodology Review
1. **Large-doc performance test can silently skip failures (High).**
   - `ensure_twenty_page_document` ignores `document_wait_for_job` failures (`|| true`), so ingestion errors/timeouts for the 20-page PDF are never surfaced (lines 69‑82). `processing_speed_large` then only asserts when a duration exists and otherwise does nothing (lines 221‑229), meaning the test passes even if the long document never processed.
   - **Recommendation:** Remove the `|| true`, enforce a status check, and fail fast when the fixture cannot be ingested. Log the captured `LAST_JOB_ERROR` so the failure is actionable.

2. **Re-upload checks do not wait for ingestion completion (High).**
   - Tests such as `deduplication`, `delete_vectors`, and `metrics_counters` call `document_upload_file` and immediately assert on dedup flags, Qdrant counts, or Prometheus counters (lines 193‑325). Because ingestion and embedding are asynchronous, these assertions can observe stale data or pass despite regressions.
   - **Recommendation:** Reuse `document_wait_for_job` after each upload and only assert once the background job reports `completed`. This also avoids polluting Prometheus/DB with half-processed documents.

3. **Concurrent upload test leaves stale status markers (Medium).**
   - `concurrent_uploads` writes `$TEST_DIR/concurrent-*.status` files when a background upload fails but never truncates or deletes them (lines 277‑312). A single historical failure poisons all future runs because `grep -c "fail" ...` keeps reading the stale file.
   - **Recommendation:** Remove any existing status files before the loop and clean them after the test to keep runs independent.

## Phase 3 – Error Handling Review
1. **Job polling suppresses actionable errors (Medium).**
   - `document_wait_for_job` tracks `LAST_JOB_ERROR` but callers never log or assert on it (lines 23‑45, 490‑492). When a job fails/ times out, the failure reason is silently dropped, leaving the operator with only a generic assertion failure later.
   - **Recommendation:** Have `document_wait_for_job` emit a structured error that includes the job id, status, and `LAST_JOB_ERROR`, or have callers print it before returning `rc=1`.

2. **Optional fixture waits mask hard failures (Medium).**
   - Both `ensure_twenty_page_document` and `ensure_failed_document_fixture` swallow `document_wait_for_job` failures with `|| true` (lines 69‑104). As a result, a broken ingestion queue would not fail Stage 3 because no caller checks the return code.
   - **Recommendation:** Let these helpers bubble up the exit code or add explicit assertions so fixture creation errors break the suite immediately.

## Phase 4 – Debugging & Observability Review
- **Lack of HTTP status logging (Low).** Tests such as `search_keyword`, `search_semantic`, and `rag_answer` assert on response bodies only and skip logging HTTP status codes except when a request writes to disk (lines 159‑189). Missing status logging slows triage when the API returns 4xx/5xx JSON with no mention in the log output.
- **Recommendation:** Capture and assert the status code (using `-w "%{http_code}"`) before parsing the response body.

## Phase 5 – Timing & Synchronization Review
- **Async resource checks race with back-end propagation (Medium).** As noted in Phase 2, `deduplication`, `delete_vectors`, and `metrics_counters` check for downstream effects immediately after upload (lines 193‑325), creating race conditions against embedding and metrics exporters. Adding targeted waits (poll job status, poll Qdrant for expected point counts with a timeout) would stabilize the suite.

## Phase 6 – Performance & Efficiency Review
- **Large temporary files are never cleaned (Medium).** `ensure_large_document_fixture` always keeps a 60 MB zero-filled PDF under `$TEST_DIR` (lines 84‑90), and `concurrent_uploads` leaves multiple generated PDFs plus `.status` files (lines 277‑312). On constrained CI workers the unused artifacts consume disk and slow future runs.
- **Recommendation:** Create these fixtures under `mktemp -d`, register a `trap` to delete them, or reuse a single on-disk artifact under version control.

## Phase 7 – Code Quality & Maintainability Review
- **Monolithic `documents_check` switch (Low).** All ~30 assertions live in one 200+ line case statement (lines 106‑332), making it difficult to extend or reuse individual checks. Extracting logical groups (ingestion, search, RAG, lifecycle) into dedicated functions would improve readability and enable selective execution.

## Phase 8 – Security & Safety Review
- No high-risk findings specific to shell injection or credential handling were observed. Inputs are mostly generated by the test harness, and sensitive headers stay in environment variables.

## Phase 9 – Integration & Dependencies Review
- Dependencies such as Qdrant and Prometheus are assumed to exist but never probed before use (lines 57‑67, 253‑264, 314‑325). A missing service yields opaque `jq` parse errors. Adding readiness probes (e.g., HEAD checks with informative error messages) would reduce support time.

## Phase 10 – Summary & Recommendations
| Severity | Issue | Impact | Recommendation |
| --- | --- | --- | --- |
| High | Large document performance test never fails when ingestion breaks | Misses regressions in async worker throughput | Fail fast when the 20-page job fails, and assert on job status before timing analysis. |
| High | Re-upload checks race ingestion and metrics | Flaky or false-positive results for dedup, deletion, and metrics | Wait for job completion and add bounded polling around Qdrant/Prometheus checks. |
| Medium | Concurrent upload status files never cleaned | Future runs fail because of stale `fail` markers; disk churn | Delete/overwrite the marker files on setup/teardown. |
| Medium | Fixture helpers swallow job failures | Stage 3 can “pass” even though ingestion jobs fail immediately | Remove `|| true` and propagate errors/log messages. |
| Medium | Large fixtures & artifacts never cleaned | Disk pressure on CI workers, slower reruns | Use `mktemp` + `trap` or reuse committed fixtures. |
| Low | Missing HTTP status assertions in search/RAG tests | Harder to triage API regressions | Capture HTTP codes alongside body assertions. |

### Quick Wins
- Fail the suite immediately when fixture ingestion fails (drop `|| true`).
- Clean `$TEST_DIR/concurrent-*` artifacts before/after the concurrent upload test.
- Capture HTTP status codes in search and RAG checks.

### Follow-up Work
- Refactor `documents_check` into smaller helper functions grouped by concern.
- Add readiness probes for Qdrant and Prometheus before issuing scroll/metrics queries.

Please let me know if you'd like me to start implementing these fixes.
