# Test Script Review: `tests/stage7.sh`

_Review conducted according to `tests/TEST_REVIEW_PLAN.md`_

## Phase 1: Initial Assessment & Understanding
- **Purpose:** Validates existence of Google Calendar sync infrastructure (DB tables/columns) and HTTP endpoints for status, OAuth connect/disconnect, and manual sync trigger.
- **Key Functions:** `test_google_sync_table_exists`, `test_google_sync_status_endpoint`, `test_google_oauth_endpoints`, `test_google_sync_state`, `test_google_event_id_field`, `test_google_sync_trigger`, orchestrated via `run_stage7`.
- **Dependencies:**
  - `psql_query`, `log`, `warn`, `success`, `error`, `run_test`, and `section` utilities from `common.sh`.
  - Environment variables `BASE_URL` and `TOKEN`.
  - PostgreSQL schema with `calendar_sync_state` and `calendar_events` tables.

## Phase 2: Testing Methodology Review
- **Organization:** Functions are short and focused, and `run_stage7` loops over declarative metadata, which keeps ordering consistent.
- **Coverage Gaps:**
  - Only checks HTTP status codes and table/column presence. No verification of response payloads (e.g., OAuth URLs, sync status contents), so regressions inside handlers will go undetected.
  - Does not simulate positive user journeys (initiating OAuth, storing sync tokens, pulling/pushing events) or negative cases (expired tokens, missing permissions).
  - Sync trigger test treats `400` and `401` as success, which hides genuine API contract regressions.
- **Assertions:** Assertions are binary (status equals `200/302/400/401`), not semantic. Lack of JSON schema or body validation reduces reliability.
- **Isolation:** Tests do not create state, so teardown is minimal; however, they rely entirely on whatever data already exists, making results highly environment-dependent.

## Phase 3: Error Handling Review
- `set -euo pipefail` is correctly enabled (line 5), preventing silent failures.
- Several checks deliberately `return 0` even when prerequisites are missing (lines 12-14, 27-29, 46-47, 75-78, 102-105). This keeps Stage 7 optional but also prevents CI from flagging partially implemented features.
- `test_google_sync_status_endpoint` mixes stdout/stderr (`2>&1`) while parsing HTTP status (lines 21-23). If curl writes warnings, `tail -1` may no longer contain an HTTP code, causing misleading `error` messages.
- No cleanup traps are necessary, but there is also no `trap` for logging overall failure context.

## Phase 4: Debugging & Observability Review
- Logging uses `log`/`success`/`warn`, which gives high-level progress updates, but response bodies are never recorded. When a status is unexpected, there is no detail about the returned payload or error message to aid debugging.
- No verbosity flag to capture full curl responses when troubleshooting OAuth redirects.
- Database assertions do not log the actual counts/column lists when they fail, obscuring root causes.

## Phase 5: Timing & Synchronization Review
- Tests assume synchronous responses; there is no waiting for background sync jobs. Triggering `/api/v1/calendar/google/sync` does not verify that jobs are queued/completed, so race conditions remain undetected.
- No retry/backoff logic; if the API briefly flaps (e.g., server cold start), the test will immediately fail without retries.

## Phase 6: Performance & Efficiency Review
- Multiple functions duplicate the same `SELECT COUNT(*) FROM information_schema.tables` query (lines 10-12 and 61-67). Caching or reusing helper logic could reduce repeated DB hits, though the impact is minor.
- Curl calls always fetch fresh responses even when only existence is needed; however, runtime remains small.

## Phase 7: Code Quality & Maintainability Review
- Code style is consistent, but there is no file-level header describing required environment setup (e.g., sourcing `common.sh`).
- Magic strings such as endpoint paths and table names are repeated; extracting them into variables would reduce typos.
- Common utilities (e.g., helper to assert table/column existence) could live in `common.sh` to deduplicate logic shared with other stages.

## Phase 8: Security & Safety Review
- Curl commands embed bearer tokens but never echo them, which is good. However, the script does not validate HTTPS certificates (default curl behavior is fine) nor sanitize environment variables.
- SQL queries interpolate literal names only, so risk is low.
- No temporary files are created.

## Phase 9: Integration & Dependencies Review
- Script assumes `psql_query` and HTTP helpers exist but never checks that `common.sh` has been sourced. If run standalone, it will fail immediately.
- There is no guard to ensure `BASE_URL`/`TOKEN` are set before tests execute, so misconfiguration results in confusing curl errors.

## Phase 10: Summary & Recommendations
### Issues (ranked by severity)
1. **High – Missing behavioral coverage:** Tests only assert endpoint/table existence and status codes, so real sync/OAuth logic can break unnoticed. Add functional flows (mock OAuth callback, verify tokens stored, ensure sync token updates, event push/pull).【F:tests/stage7.sh†L18-L108】
2. **Medium – Weak assertions/logging:** Lack of response-body validation and minimal failure context hinders debugging and allows incorrect payloads to pass. Capture and inspect JSON bodies, log key fields when mismatched, and store artifacts on failure.【F:tests/stage7.sh†L18-L105】
3. **Medium – Intentional success on missing features:** Returning success when tables/endpoints are absent (lines 12-14, 27-29, 46-47, 75-78, 102-105) prevents CI from catching regressions once Stage 7 ships. Consider gating with feature flags instead of silently passing.【F:tests/stage7.sh†L7-L107】
4. **Low – Redundant DB queries and magic strings:** Repeating information-schema lookups and hardcoding endpoint paths increases maintenance cost. Extract helper functions/constants in `common.sh`.【F:tests/stage7.sh†L7-L108】
5. **Low – Missing environment validation:** Script never ensures `BASE_URL`, `TOKEN`, or `psql_query` are available, leading to opaque failures when prerequisites are missing. Add preflight checks and clearer error messages.【F:tests/stage7.sh†L18-L108】

### Quick Wins
- Add a header comment documenting required env vars and sourcing order.
- Log curl response bodies when non-2xx codes appear.
- Introduce helper functions for `assert_table_exists` / `assert_column_exists` to reduce duplication.

### Refactoring Opportunities
- Implement reusable JSON assertion helpers (e.g., `expect_json_field`) in `common.sh` and use them for all HTTP tests.
- Encapsulate OAuth and sync flows into scenario-based tests (e.g., `run_google_oauth_flow`) instead of isolated endpoint pings.

### Follow-up Actions
- Decide whether Stage 7 is optional; if not, remove `return 0` paths so CI fails when endpoints/tables disappear.
- Mock Google APIs or provide a sandbox environment so the tests can exercise real sync logic without external dependencies.

---
Please confirm if you would like me to start implementing any of the recommended fixes.
