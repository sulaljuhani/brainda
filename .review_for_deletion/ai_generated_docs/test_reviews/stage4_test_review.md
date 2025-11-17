# Stage 4 Test Review

_Review scope_: `tests/stage4.sh`

## Phase 1 – Initial Assessment & Metadata
- **Purpose**: Exercises end-to-end backup creation/restore, retention cleanup hooks, and Prometheus metrics/SLO checks for reminders, ingestion, and vector search.
- **Key routines**: `discover_latest_backup`, `run_backup_job`, `stage4_restore_temp_db`, `metric_value`, and `stage4_check`'s large case statement consumed by `run_stage4`.
- **Dependencies**: Relies on running Docker services (`brainda-postgres`, `brainda-beat`, `brainda-worker`), backup scripts under `backups/`, metrics endpoint (`METRICS_URL`), API base URL & auth (`BASE_URL`, `TOKEN`), plus histogram helpers (`histogram_quantile_from_metrics`) provided by `common.sh`.

## Phase 2 – Testing Methodology
- Comprehensive matrix of metrics, SLO, backup, and retention checks wired through `run_test`, but some tests share state (e.g., backup artifacts reused across assertions) without explicit sequencing comments.
- Only one positive-path restore verification exists; no negative test that proves failures are caught when artifacts missing.
- Metrics increments (`notes_created_total`, `api_request_duration_seconds_count`) rely on immediate counter availability; there is no wait/poll to guard against asynchronous scraping delays.

## Phase 3 – Error Handling
- Script uses `set -euo pipefail` and most subprocesses are wrapped with assertions, yet several commands intentionally swallow failures via `|| true` without explaining the acceptable failure modes (e.g., `retention_cleanup_manual` Celery call, manifest greps).
- No `trap` cleanups or log preservation when `run_backup_job`/`stage4_restore_temp_db` fail; logs are written under `/tmp` but never surfaced automatically.

## Phase 4 – Debugging & Observability
- `run_test` + `section` (from `common.sh`) provide basic progress logs, but individual checks almost never echo contextual state (e.g., which backup timestamp is under test or metric values read), limiting diagnosability when thresholds fail.
- Failure artifacts like `/tmp/backup-run.log` and `/tmp/restore-run.log` are not attached or hinted at, so operators must know to fetch them manually.

## Phase 5 – Timing & Synchronization
- Metrics increment checks fire API requests and immediately read counters without any retry/backoff, risking flakes if Prometheus scraping lags or counters are eventually consistent.
- Restore flow does not wait for postgres to finish applying WAL beyond the `restore.sh` invocation; there is no health check verifying the restored DB is fully ready prior to querying `pg_database`.

## Phase 6 – Performance & Efficiency
- The case statement repeatedly calls `curl -sS "$METRICS_URL"` for each metric/SLO (sometimes multiple times per check). Fetching metrics once per run or caching them inside `stage4_check` would drastically reduce runtime and load on the metrics endpoint.
- `discover_latest_backup` scans the entire `postgres/backup-*.dump` directory with `ls | sort` for every check, which becomes expensive when many artifacts accumulate; caching `LATEST_BACKUP_TS` after the first lookup would avoid redundant IO.

## Phase 7 – Code Quality & Maintainability
- Logic is monolithic inside `stage4_check`; per-feature helpers (e.g., `assert_metric_defined`, `assert_backup_artifact`) would improve readability and reuse.
- No documentation describes expected environment variables or prerequisites beyond top-level comments, and there are several inline string literals (metric names, Docker container names) that should live in shared constants to avoid drift.

## Phase 8 – Security & Safety
- Commands such as `metric_value` interpolate metric names directly into `grep` without escaping regex characters. Present names are safe, but defensive quoting (e.g., `grep -F`) would block future issues.
- Temporary database `vib_restore_test` is never dropped, leaving restored customer data sitting in Postgres indefinitely and potentially exposing sensitive rows if the instance is multi-tenant.

## Phase 9 – Integration & Dependencies
- The script assumes `BASE_URL`, `TOKEN`, `BACKUP_ROOT`, `METRICS_URL`, and SLO thresholds are exported by the caller but never validates them upfront. When any variable is missing the resulting failures are opaque (e.g., `curl -sS "$METRICS_URL"` just errors).
- `common.sh` is presumably sourced by the stage runner, yet this file calls helper functions (`run_test`, `section`, `assert_*`) without verifying the include succeeded, so executing `tests/stage4.sh` standalone will crash.

## Phase 10 – Issues & Recommendations
### Critical
1. **Temporary restore database never cleaned up** – `stage4_restore_temp_db` creates/replicates `vib_restore_test` but the test never drops it, so repeated runs can accumulate stale clones, leak sensitive data, or fail if the restore script refuses to overwrite an existing DB. Add teardown logic (drop DB in `finally`/`trap`) or perform restore inside a disposable container.【F:tests/stage4.sh†L184-L190】

### High
2. **No validation for required environment variables** – Missing `METRICS_URL`, `BASE_URL`, `TOKEN`, `BACKUP_ROOT`, or SLO thresholds manifest as confusing `curl`/`assert_*` failures. Introduce an upfront `require_env` helper to abort early with actionable messaging.【F:tests/stage4.sh†L39-L228】
3. **Metrics polling prone to flakes** – Tests assume counters update instantly after issuing API calls, yet no waits or retries exist, causing race conditions under Prometheus scrape lag. Wrap increments with polling (sleep + retry) or query the API directly for authoritative counts.【F:tests/stage4.sh†L61-L95】

### Medium
4. **Metrics endpoint fetched repeatedly** – Each case re-downloads the entire metrics payload, which is slow and hammers the service. Cache a single scrape per test run or per logical group to speed Stage 4 and reduce noise.【F:tests/stage4.sh†L50-L150】
5. **Backup discovery re-scans filesystem** – Every artifact assertion re-runs `discover_latest_backup`, which shells out to `ls | sort | tail`. Cache the timestamp once or add memoization to avoid O(N) scans per check when many snapshots exist.【F:tests/stage4.sh†L8-L177】
6. **Lack of structured logging/context** – Assertions do not print the metric values or file paths under evaluation, making triage difficult. Logging the timestamp, metric numbers, or container command output before asserting would improve observability.【F:tests/stage4.sh†L46-L233】

### Low / Quick Wins
7. **Regex-sensitive `grep` usage** – Switch to `grep -F` (literal) in `metric_value` and manifest checks to avoid accidental regex expansion when metric names change.【F:tests/stage4.sh†L39-L44】
8. **`|| true` swallowing command failures without commentary** – Several commands intentionally ignore exit codes but the rationale is undocumented; add comments or tighten error handling to clarify expected behavior.【F:tests/stage4.sh†L10-L227】

### Next Steps
Please review and confirm which issues you’d like prioritized so I can proceed with fixes (drop/create cleanup, env validation, caching, etc.).
