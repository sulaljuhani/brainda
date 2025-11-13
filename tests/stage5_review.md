# Stage 5 Test Script Review

**File Reviewed:** `tests/stage5.sh`
**Review Plan Used:** `tests/TEST_REVIEW_PLAN.md`

## Phase 1: Initial Assessment & Understanding
- **Purpose:** Validates idempotency key behavior, reminder creation concurrency, and light-weight mobile/session readiness checks for the reminders API. 【F:tests/stage5.sh†L1-L315】
- **Key Functions:** `test_idempotency_*` variants exercise CRUD flows; `test_mobile_api_endpoints` and `test_session_token_format` provide smoke checks. 【F:tests/stage5.sh†L7-L315】
- **Dependencies:** Relies on `curl`, `jq`, Postgres via `psql_query`, `docker exec vib-worker`, shared helpers from `tests/common.sh`, and environment values (`BASE_URL`, `TOKEN`, `TEST_DIR`, `TIMESTAMP`). 【F:tests/stage5.sh†L19-L315】

## Phase 2: Testing Methodology Review
- **Organization:** Tests are defined as shell functions and registered in `run_stage5`. However, there is no grouping/ordering based on destructive state, and cleanup is absent so later runs inherit prior reminders. 【F:tests/stage5.sh†L297-L315】
- **Coverage:** Positive idempotency scenarios are covered, but negative/error branches (e.g., invalid key, expired key reuse, mobile auth failures) are missing. Session/mobile checks only confirm presence of tables/endpoints without exercising behaviors.
- **Assertions:** Several tests never assert HTTP status or response structure before relying on parsed IDs, so failures could go unnoticed (see Phase 3).
- **Isolation:** Database writes (reminders, idempotency keys) are never deleted or namespaced, leading to cumulative rows across runs and potential clashes for title-based COUNT queries.

## Phase 3: Error Handling Review
- `set -euo pipefail` is present, but commands executed inside subshells/background jobs bypass it.
- **Missing HTTP Status Checks (High):** `test_idempotency_duplicate_prevention`, `test_idempotency_header_replay`, `test_idempotency_aggressive_retry`, `test_idempotency_different_keys`, and `test_idempotency_key_expiry` never inspect HTTP codes, so a 500 response would still be treated as success and parsed with `jq`. 【F:tests/stage5.sh†L58-L260】
- **Background job failures ignored (Medium):** The aggressive retry test spawns 10 parallel curls but only waits for completion; it never checks individual exit codes or contents of the captured files, so failures/timeouts won’t fail the test. 【F:tests/stage5.sh†L143-L193】
- **Exit codes:** Several “warn” paths (`test_idempotency_header_replay`, `test_idempotency_key_expiry`, `test_idempotency_cleanup_job`, `test_session_token_format`) always return 0, even when core functionality is missing, making it impossible to gate on regression severity. 【F:tests/stage5.sh†L110-L295】

## Phase 4: Debugging & Observability Review
- Responses are only printed on failure within `test_idempotency_create_reminder`; other tests do not capture bodies or headers beyond a single header file, reducing debuggability.
- There is no verbosity flag; background curl outputs in the aggressive test are redirected to files but never summarized, leaving artifacts without context.
- Header captures (`headers-dup.txt`, `replay-headers.txt`) are never cleaned up and only partially logged.

## Phase 5: Timing & Synchronization Review
- Aggressive retry test uses a busy-wait loop with fixed 0.5s sleep and an arbitrary 2-second delay before DB validation, which may flake depending on workload. 【F:tests/stage5.sh†L161-L193】
- No polling/backoff when waiting for reminder creation or DB propagation; tests assume immediate consistency.

## Phase 6: Performance & Efficiency Review
- `sleep 2` after concurrent requests extends runtime even when unnecessary; a polling query for reminder count would be faster and more reliable. 【F:tests/stage5.sh†L182-L188】
- Repeated payload construction via inline `jq` occurs in every test; extracting to a helper would reduce duplication and JSON generation cost.

## Phase 7: Code Quality & Maintainability Review
- Duplicate logic for computing `due_utc`, building payload JSON, and parsing IDs appears in every test; these should live in helpers within `common.sh` or local functions.
- Temporary files (`headers-dup.txt`, `replay-headers.txt`, `aggressive-*.json`) are written directly inside `$TEST_DIR` but never deleted, causing clutter between runs.
- Comments mention unimplemented features yet there is no TODO/skip annotation clarifying when warnings should become failures.

## Phase 8: Security & Safety Review
- SQL queries interpolate `$title`/`$idem_key` directly; while values originate from the script, quoting via `psql_query` should use parameterization or at least `sql_escape` helpers to avoid breakage if titles contain apostrophes.
- `docker exec vib-worker ...` assumes access without checking container existence or permissions; failures would emit noisy stack traces without context.

## Phase 9: Integration & Dependencies Review
- Script assumes `tests/common.sh` has defined `psql_query`, `log`, and `run_test`, but `tests/stage5.sh` does not source it itself; it relies on the runner to do so, which should be documented in the header comment.
- External dependencies (`curl`, `jq`, `docker`, `psql`) are not verified before use.

## Phase 10: Summary & Recommendations
### Issues Found
1. **High:** Missing HTTP status/response assertions across most tests allow silent false positives. 【F:tests/stage5.sh†L58-L260】
2. **Medium:** Aggressive retry background jobs and captured files are never validated, so concurrency regressions may pass unnoticed. 【F:tests/stage5.sh†L143-L193】
3. **Medium:** Tests leave behind reminders, idempotency keys, and temporary files, harming idempotency and making reruns stateful. 【F:tests/stage5.sh†L67-L260】
4. **Low:** Repeated JSON construction and SQL interpolation reduce maintainability and increase risk of syntax errors; these should be abstracted.

### Recommendations & Quick Wins
- Introduce a shared helper to POST reminders that returns both HTTP status and parsed payload, so every test can assert success/failure consistently.
- Track created reminder IDs and delete them (or run inside a transaction) during teardown; clean up temp files with `trap`.
- In the aggressive retry test, collect exit codes (e.g., via `wait -n`) and parse the JSON files to ensure only one ID is returned.
- Replace fixed sleeps with polling loops that respect timeouts; log timing info for easier debugging.

### Follow-up Actions
- Decide whether warnings for replay headers/expiry/cleanup should become failures at Stage 5 or later; document acceptance criteria accordingly.
- Add dependency checks (psql, curl, docker) at the top of the script to provide actionable errors.

**Action:** Please confirm if you’d like me to start implementing these fixes; several require changes in both `tests/stage5.sh` and shared helpers.
