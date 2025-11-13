# Stage 6 Test Script Review (tests/stage6.sh)

_Review executed according to [`tests/TEST_REVIEW_PLAN.md`](../TEST_REVIEW_PLAN.md)._ 

## Phase 1: Initial Assessment & Understanding
- **Purpose:** Validates CRUD endpoints for calendar events, RRULE handling, reminder linking, timezone storage, and table schema expectations. The script is organized as a set of shell functions registered inside `run_stage6`. 【F:tests/stage6.sh†L2-L382】
- **Key behaviors covered:** table existence, create/read/update/delete flows, RRULE creation/expansion/validation, reminder linkage, weekly view listing, timezone persistence, and user isolation. 【F:tests/stage6.sh†L7-L357】
- **External dependencies:** relies on `curl`, `jq`, and `psql_query` helper plus environment variables (`BASE_URL`, `TOKEN`, `TIMESTAMP`). Direct SQL access is required for verification. 【F:tests/stage6.sh†L19-L357】

## Phase 2: Testing Methodology Review
1. **Test independence concerns (High):** `test_calendar_event_in_db` and `test_calendar_event_update` depend on the globally cached `CALENDAR_EVENT_ID` populated by `test_calendar_event_create`, so they cannot run in isolation or be re-ordered without manual setup. 【F:tests/stage6.sh†L51-L108】
2. **Insufficient assertions (Medium):** Several cases only assert HTTP 200 without validating payloads or side effects (`test_calendar_event_list`, `test_calendar_weekly_view`, RRULE weekly test), leading to false positives if the API returns empty/default data. 【F:tests/stage6.sh†L63-L84】【F:tests/stage6.sh†L177-L195】【F:tests/stage6.sh†L307-L319】
3. **No teardown / data reuse (Medium):** Every RRULE and reminder test creates new persistent rows without cleanup, which can bloat the calendar tables and leak into other runs. There is no `trap` or delete step for the created resources. 【F:tests/stage6.sh†L110-L342】

## Phase 3: Error Handling Review
1. **Missed HTTP error detection (High):** `test_calendar_rrule_expansion` and `test_calendar_event_delete` ignore the POST response status entirely, so failures during event creation will go unnoticed and manifest later in the test. 【F:tests/stage6.sh†L110-L211】
2. **Partial validation warnings:** Several functions log warnings for unexpected states (e.g., empty list, invalid RRULE acceptance) but still report test success even though core functionality may be missing, reducing signal when regressions occur. 【F:tests/stage6.sh†L77-L84】【F:tests/stage6.sh†L227-L254】

## Phase 4: Debugging & Observability Review
- **Limited context on failure (Medium):** Except for the creation helper, most tests drop the HTTP body, making it difficult to debug server errors (e.g., weekly view, timezone). Capturing response JSON (even when the status is 200) would aid root-cause analysis. 【F:tests/stage6.sh†L63-L343】
- **No verbosity toggles:** The script depends on shared logging helpers but offers no per-test verbose mode or artifact collection (responses, SQL queries) when an assertion fails.

## Phase 5: Timing & Synchronization Review
- **Fixed sleeps instead of polling (Medium):** RRULE expansion uses a hard-coded `sleep 1` to wait for background expansion, which may be flaky under load; a polling loop with timeout against the API would be more reliable. 【F:tests/stage6.sh†L208-L231】

## Phase 6: Performance & Efficiency Review
- **Redundant event creation (Low):** Each test rebuilds payloads and hits the API sequentially, even when the same helper could create reusable fixtures. Consolidating setup would shorten runtime and reduce API load. 【F:tests/stage6.sh†L19-L342】
- **No cleanup = growing tables (Medium):** As noted earlier, lack of teardown accumulates rows and can slow subsequent test passes.

## Phase 7: Code Quality & Maintainability Review
- **Duplicate payload construction (Low):** JSON payload generation for events repeats across multiple tests; extracting helper functions (e.g., `create_calendar_event()`) in `common.sh` would reduce duplication and mistakes. 【F:tests/stage6.sh†L19-L342】
- **Magic strings:** Endpoint paths and status codes are hard-coded inline; centralizing them would make updates less error-prone.

## Phase 8: Security & Safety Review
- **Direct SQL string interpolation (Low):** Values such as `CALENDAR_EVENT_ID` and user-provided titles are interpolated directly into SQL without escaping. Even though inputs originate from the script, wrapping them with parameterization helpers (or at least `psql` `\gset`) would be safer. 【F:tests/stage6.sh†L58-L343】
- **Reminder linking bypasses API (Medium):** The reminder link test updates `reminders.calendar_event_id` directly via SQL instead of exercising the intended API pathway, so it cannot detect authorization or validation bugs in the linking feature. 【F:tests/stage6.sh†L292-L303】

## Phase 9: Integration & Dependencies Review
- **Dependency checks missing (Low):** The script assumes `jq`, `curl`, and DB connectivity exist but never verifies prerequisites at the top of the stage (contrast with other stages that sometimes run smoke checks).
- **common.sh integration:** `run_stage6` assumes logging helpers, but there is no local documentation reminding contributors to source `tests/common.sh` before invoking these functions.

## Phase 10: Summary & Recommendations
### Issues Found
- **Critical:** _None identified._
- **High:**
  1. Tests rely on shared global state (`CALENDAR_EVENT_ID`), breaking isolation and making single-test execution brittle. 【F:tests/stage6.sh†L51-L108】
  2. Event creation errors are silently ignored in multiple tests, leading to misleading passes. 【F:tests/stage6.sh†L110-L211】
- **Medium:**
  1. Many tests only check HTTP 200 instead of validating bodies/side effects. 【F:tests/stage6.sh†L63-L319】
  2. Persistent data is never cleaned up, so stage reruns pollute the database. 【F:tests/stage6.sh†L110-L342】
  3. Reminder linking bypasses the API by editing DB rows directly. 【F:tests/stage6.sh†L292-L303】
  4. Fixed `sleep 1` makes RRULE expansion flaky. 【F:tests/stage6.sh†L208-L231】
- **Low:**
  1. Duplicate payload construction & magic strings reduce maintainability. 【F:tests/stage6.sh†L19-L342】
  2. Lack of dependency checks/verbosity toggles hampers debugging.

### Specific Recommendations
1. Introduce helper functions to create/delete events and ensure each test provisions its own data and cleans it up (possibly via `trap`).
2. Update RRULE, delete, and reminder tests to assert on both HTTP status and response bodies, and surface server responses on failure.
3. Replace fixed sleeps with a polling helper that queries the list endpoint until the expected count appears or a timeout is reached.
4. Cover the reminder linking API path end-to-end instead of manipulating the database.
5. Add guardrails (dependency checks, verbose flag, SQL parameterization) to make failures easier to interpret.

### Quick Wins
- Reuse the existing creation logic inside helper functions to eliminate repeated payload snippets.
- Capture the HTTP response bodies (e.g., by logging to temp files) whenever an assertion fails.

### Refactoring Opportunities
- Move shared calendar/reminder fixture helpers into `tests/common.sh` to enforce consistent setup/teardown.
- Consider grouping RRULE-specific tests into their own function that prepares + cleans a dedicated test calendar.

### Follow-up Actions
- Decide whether calendar reminder linking should be API-driven or DB-driven and adjust the test accordingly.
- Determine acceptable retention/cleanup strategy for calendar test data to keep staging DBs lean.

**Action:** Please confirm whether you want me to start implementing these fixes; once approved I can update `tests/stage6.sh` accordingly.
