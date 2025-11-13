# Stage 2 Test Script Review

## Pre-Review Setup
- **File Reviewed:** `tests/stage2.sh`

---

## Phase 1: Initial Assessment & Understanding
- **Primary Scope:** Validates reminder creation, deduplication, snoozing, recurring schedules, notification delivery, metrics exposure, and device registration for Stage 2 of the acceptance suite. 【F:tests/stage2.sh†L1-L352】
- **Key Helpers & Tests:** Utility helpers (`create_chat_reminder`, `stage2_wait_for_log`, `create_unique_reminder`) plus 27 individual `test_*` cases invoked through `run_stage2`. 【F:tests/stage2.sh†L7-L352】
- **External Dependencies:**
  - REST APIs under `$BASE_URL/api/v1/*` and chat endpoint for natural language reminder creation. 【F:tests/stage2.sh†L12-L190】
  - PostgreSQL (`psql_query`, docker exec) and Prometheus metrics endpoints for validation. 【F:tests/stage2.sh†L96-L313】
  - Dockerized orchestrator logs (`docker logs vib-orchestrator`). 【F:tests/stage2.sh†L31-L35】

---

## Phase 2: Testing Methodology Review
- **Organization:** Tests live as shell functions and are looped in `run_stage2`. Setup relies heavily on implicit fixtures (`ensure_reminder_fixture`, `ensure_device_registered`). 【F:tests/stage2.sh†L38-L352】
- **Coverage Observations:** Covers core CRUD, scheduling, recurrence, metrics, and push delivery happy paths. Negative paths exist for deduplication and DB constraints, but log-based verifications lack robustness.
- **Assertions:** Many assertions only check basic equality. Some checks (e.g., `test_device_test_notification`) explicitly allow a `404` and skip validation entirely, leaving gaps.
- **Independence:** `test_reminder_snooze_reschedules` assumes that `test_reminder_snooze_updates_due` already snoozed a reminder and does not perform its own action, leading to ordering dependencies. 【F:tests/stage2.sh†L122-L140】

---

## Phase 3: Error Handling Review
- `set -euo pipefail` is enabled. 【F:tests/stage2.sh†L5】
- Failures from helper commands (curl/psql) are generally captured via assertions. However, `stage2_wait_for_log` swallows errors (`|| true`) and returns `0`, masking `docker logs` failures. 【F:tests/stage2.sh†L31-L35】
- `test_device_test_notification` treats HTTP 404 as success, which may hide real regressions in environments that should have devices registered. 【F:tests/stage2.sh†L204-L213】
- No traps/cleanup blocks exist despite numerous reminders/devices created.

---

## Phase 4: Debugging & Observability Review
- Logging relies on `run_test`/`success`/`error` wrappers from `common.sh` (adequate for pass/fail messaging).
- No contextual logging is captured when metrics/log-based assertions fail; we only see numeric comparisons. Capturing offending API responses/log snippets would improve debuggability.
- `stage2_wait_for_log` only reports counts, making it impossible to see the actual log lines responsible for failures without re-running manually. 【F:tests/stage2.sh†L31-L35】

---

## Phase 5: Timing & Synchronization Review
1. **Log Polling Gaps:** `test_reminder_scheduler_entry` and `test_reminder_snooze_reschedules` call `stage2_wait_for_log` once with no retry or wait, so transient log delays cause flakes. 【F:tests/stage2.sh†L50-L55】【F:tests/stage2.sh†L136-L140】
2. **Metrics Races:** `test_reminder_metrics_created_total` and `test_reminder_metrics_deduped_total` hit Prometheus immediately after API calls. Because scraping is asynchronous, the counter may not increment yet. No polling/backoff is implemented, which leads to nondeterministic failures. 【F:tests/stage2.sh†L264-L282】
3. **Baseline-less Log Checks:** `stage2_wait_for_log` returns cumulative counts without capturing a baseline before actions, so tests cannot distinguish new events from old ones. This opens the door for false positives/negatives depending on log retention. 【F:tests/stage2.sh†L31-L55】【F:tests/stage2.sh†L136-L140】

---

## Phase 6: Performance & Efficiency Review
- Multiple tests create reminders or devices without cleanup, which can bloat DB state over repeated runs. Consider centralized teardown or temporary test user separation.
- Polling is minimal (only a single `sleep 5` in smart defaults and `wait_for_notification_delivery` later), so runtime is acceptable, but adding smarter waits (with exponential backoff) would mitigate flakes while keeping runtime bounded.

---

## Phase 7: Code Quality & Maintainability Review
- Formatting is consistent, but helper abstractions are underused. Example: log polling logic duplicated in multiple tests; should live in `common.sh` as a `wait_for_log_contains keyword timeout` helper.
- Missing comments on complex DB joins (e.g., lag calculation query) reduce readability. 【F:tests/stage2.sh†L230-L250】
- Magic numbers (e.g., `sleep 5`, `--tail 400`, `wait_for_notification_delivery ... 150`) lack explanation or configuration knobs.

---

## Phase 8: Security & Safety Review
- `docker logs` and SQL queries interpolate IDs without quoting, but IDs originate from trusted fixtures. No user input is passed unsafely.
- Temporary files (`$TEST_DIR/chat-reminder.json`) are reused but not cleared; ensure `$TEST_DIR` is per-run to avoid leaks.

---

## Phase 9: Integration & Dependencies Review
- Script assumes `docker`, `psql`, `jq`, `awk`, and Prometheus endpoints are available. No preflight checks ensure these commands exist.
- `common.sh` helpers (e.g., `ensure_reminder_fixture`, `wait_for_notification_delivery`) are used, but `stage2_wait_for_log` duplicates functionality that could live alongside them for better reuse.

---

## Phase 10: Summary & Recommendations

### Issues & Severity
1. **Lack of Wait/Polling Around Scheduler & Snooze Logs (High):** Single-shot log checks regularly miss asynchronous events and make Stage 2 flaky. Add a helper that polls `docker logs` with a timeout and ensures new hits appear after the action. 【F:tests/stage2.sh†L31-L55】【F:tests/stage2.sh†L136-L140】
2. **Ordering-Dependent Snooze Test (High):** `test_reminder_snooze_reschedules` never snoozes a reminder itself, so it silently relies on `test_reminder_snooze_updates_due` running immediately before it. Introduce its own `create_unique_reminder` + snooze call so tests can run independently. 【F:tests/stage2.sh†L122-L140】
3. **Metrics Counters Polled Without Wait (Medium):** `test_reminder_metrics_created_total` and `test_reminder_metrics_deduped_total` scrape Prometheus immediately after API requests, so the scrape interval dictates flakiness. Implement a `wait_for_metric_increment` helper with retry/backoff. 【F:tests/stage2.sh†L264-L282】
4. **Baseline-less Log Counting (Medium):** `stage2_wait_for_log` returns total occurrences without subtracting a baseline, meaning old log entries can satisfy new tests. Capture counts before actions and compare deltas to prevent false positives. 【F:tests/stage2.sh†L31-L55】
5. **404 Handling Masks Device Regression (Low):** Treating HTTP 404 as a success in `test_device_test_notification` hides bugs when devices should exist; make this behavior configurable or assert absence explicitly. 【F:tests/stage2.sh†L204-L213】

### Quick Wins
- Centralize log polling with timeout/baseline capture.
- Add Prometheus polling helper (reuse for other metrics tests).
- Make snooze/log tests self-contained.

### Follow-Up
- Document teardown strategy (or add cleanup script) to avoid DB bloat from repeated reminder creation.

**Action:** Please let me know if you’d like me to implement these fixes; I can start as soon as I receive approval.
