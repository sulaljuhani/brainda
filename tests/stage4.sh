#!/usr/bin/env bash
# Stage 4: Backups + Retention + Observability Tests
# Tests backup/restore, retention policies, and metrics/SLOs

set -euo pipefail

# Enable debug mode if requested
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

RESTORE_DB_NAME="${RESTORE_DB_NAME:-vib_restore_test}"
METRIC_RETRY_ATTEMPTS=${METRIC_RETRY_ATTEMPTS:-5}
METRIC_RETRY_DELAY=${METRIC_RETRY_DELAY:-3}
METRICS_CACHE_TTL=${METRICS_CACHE_TTL:-5}

require_env_vars() {
  local missing=()
  for var in "$@"; do
    if [[ -z "${!var:-}" ]]; then
      missing+=("$var")
    fi
  done
  if (( ${#missing[@]} > 0 )); then
    error "Missing required environment variables: ${missing[*]}"
    exit 1
  fi
}

fetch_metrics_payload() {
  local now ttl refresh
  refresh="${1:-}"
  ttl="$METRICS_CACHE_TTL"
  now=$(date +%s)
  if [[ -z "${METRICS_CACHE_TIMESTAMP:-}" || -z "${METRICS_PAYLOAD:-}" ]]; then
    refresh="force"
  fi
  if [[ "$refresh" == "force" || $(( now - METRICS_CACHE_TIMESTAMP )) -ge "$ttl" ]]; then
    METRICS_PAYLOAD=$(curl -sS "$METRICS_URL")
    METRICS_CACHE_TIMESTAMP=$now
  fi
  printf '%s\n' "$METRICS_PAYLOAD"
}

metric_value() {
  local metric="$1"
  local refresh="${2:-}"
  local payload
  if [[ "$refresh" == "refresh" ]]; then
    payload=$(fetch_metrics_payload force)
  else
    payload=$(fetch_metrics_payload)
  fi
  printf '%s\n' "$payload" | awk -v name="$metric" '$1 ~ ("^"name"\\{"|"^"name" ") {s+=$NF} END {print s}'
}

cleanup_restore_db() {
  docker exec vib-postgres psql -U "${POSTGRES_USER:-vib}" -d postgres -c "DROP DATABASE IF EXISTS \"$RESTORE_DB_NAME\";" >/dev/null 2>&1 || true
}

discover_latest_backup() {
  local force="${1:-}"
  if [[ -n "${LATEST_BACKUP_TS:-}" && "$force" != "force" ]]; then
    return
  fi
  local latest
  latest=$(ls -1 "$BACKUP_ROOT"/postgres/backup-*.dump 2>/dev/null | sort | tail -n1 || true)
  if [[ -n "$latest" ]]; then
    latest=${latest##*backup-}
    latest=${latest%.dump}
    LATEST_BACKUP_TS="$latest"
  fi
}

run_backup_job() {
  mkdir -p "$BACKUP_ROOT"
  BACKUP_DIR="$BACKUP_ROOT" bash backups/backup.sh >/tmp/backup-run.log 2>&1
  discover_latest_backup force
}

stage4_restore_temp_db() {
  local ts="$1"
  if [[ -z "$ts" ]] || [[ "$ts" == "null" ]]; then
    discover_latest_backup
    ts="$LATEST_BACKUP_TS"
  fi
  [[ -z "$ts" ]] && return 1
  cleanup_restore_db
  POSTGRES_DB="$RESTORE_DB_NAME" \
  POSTGRES_CONTAINER="vib-postgres" \
  SERVICES_TO_STOP="" \
  COMPOSE_CMD="true" \
  BACKUP_DIR="$BACKUP_ROOT" \
  bash backups/restore.sh "$ts" </dev/null >/tmp/restore-run.log 2>&1
}

wait_for_metric_increase() {
  local metric="$1"
  local before="$2"
  local description="$3"
  local attempt=1
  local current="$before"
  while (( attempt <= METRIC_RETRY_ATTEMPTS )); do
    current=$(metric_value "$metric" refresh || echo 0)
    if float_greater_than "${current:-0}" "${before:-0}"; then
      success "$description"
      return 0
    fi
    sleep "$METRIC_RETRY_DELAY"
    ((attempt++))
  done
  assert_greater_than "${current:-0}" "${before:-0}" "$description" || return 1
}

stage4_check() {
  local check="$1"
  local rc=0
  case "$check" in
    metrics_defined)
      local required=(reminder_fire_lag_seconds push_delivery_success_total document_ingestion_duration_seconds vector_search_duration_seconds retention_cleanup_total)
      local payload
      payload=$(fetch_metrics_payload force)
      for metric in "${required[@]}"; do
        local count
        count=$(printf '%s\n' "$payload" | grep -Fc "$metric" || true)
        if [[ "${count:-0}" -eq 0 ]]; then
          error "Metric $metric missing"
          rc=1
        fi
      done
      ;;
    metrics_non_zero)
      # Create a note to ensure metric increments
      local before
      before=$(metric_value "notes_created_total" refresh || echo 0)
      local payload='{"title":"Metrics Test Note","body":"Testing metrics","tags":[]}'
      curl -sS -X POST "$BASE_URL/api/v1/notes" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$payload" >/dev/null 2>&1 || true
      if ! wait_for_metric_increase "notes_created_total" "${before:-0}" "Notes created metric non-zero"; then
        rc=1
      fi
      ;;
    metrics_histograms)
      local content
      content=$(fetch_metrics_payload | grep -F 'reminder_fire_lag_seconds_bucket' || true)
      assert_not_empty "$content" "Reminder fire lag histogram exported" || rc=1
      ;;
    metrics_gauges)
      local gauges=(postgres_connections redis_memory_bytes celery_queue_depth)
      for g in "${gauges[@]}"; do
        local val
        val=$(metric_value "$g" || echo "")
        if [[ -z "$val" ]]; then
          warn "Gauge $g missing"
          rc=1
        fi
      done
      ;;
    metrics_counters)
      local before
      before=$(metric_value "api_request_duration_seconds_count" refresh || echo 0)
      curl -sS "$BASE_URL/api/v1/health" >/dev/null
      if ! wait_for_metric_increase "api_request_duration_seconds_count" "${before:-0}" "API request counter increments"; then
        rc=1
      fi
      ;;
    slo_reminder_fire_lag)
      local metrics
      metrics=$(fetch_metrics_payload force)
      export METRIC_NAME="reminder_fire_lag_seconds"
      export METRIC_QUANTILE="0.95"
      REMINDER_FIRE_LAG_P95=$(echo "$metrics" | histogram_quantile_from_metrics)
      if [[ "$REMINDER_FIRE_LAG_P95" != "nan" ]]; then
        assert_less_than "$REMINDER_FIRE_LAG_P95" "$REMINDER_FIRE_LAG_TARGET" "Reminder fire lag p95 <$REMINDER_FIRE_LAG_TARGET" || rc=1
      else
        warn "Reminder lag metric lacks samples"
      fi
      ;;
    slo_push_success)
      if [[ -z "$PUSH_SUCCESS_RATE" || "$PUSH_SUCCESS_RATE" == "unknown" ]]; then
        local success failure total rate
        success=$(metric_value "push_delivery_success_total" || echo 0)
        failure=$(metric_value "push_delivery_failure_total" || echo 0)
        total=$(awk -v s="${success:-0}" -v f="${failure:-0}" 'BEGIN{print s+f}')
        if float_greater_than "${total:-0}" "0"; then
          rate=$(awk -v s="$success" -v t="$total" 'BEGIN{printf "%.3f", (t==0?0:s/t)}')
          PUSH_SUCCESS_RATE="$rate"
        fi
      fi
      if [[ "$PUSH_SUCCESS_RATE" != "unknown" ]]; then
        assert_greater_than "$PUSH_SUCCESS_RATE" "$PUSH_SUCCESS_TARGET" "Push success rate above target" || rc=1
      else
        warn "Push success rate unavailable"
      fi
      ;;
    slo_document_ingestion)
      local metrics
      metrics=$(fetch_metrics_payload force)
      export METRIC_NAME="document_ingestion_duration_seconds"
      export METRIC_QUANTILE="0.95"
      DOC_INGESTION_P95=$(echo "$metrics" | histogram_quantile_from_metrics)
      if [[ "$DOC_INGESTION_P95" != "nan" ]]; then
        assert_less_than "$DOC_INGESTION_P95" "$DOC_INGESTION_TARGET" "Document ingestion p95 <$DOC_INGESTION_TARGET" || rc=1
      else
        warn "Document ingestion histogram empty"
      fi
      ;;
    slo_vector_search)
      if [[ -z "$VECTOR_SEARCH_P95" || "$VECTOR_SEARCH_P95" == "unknown" ]]; then
        local metrics
        metrics=$(fetch_metrics_payload force)
        export METRIC_NAME="vector_search_duration_seconds"
        export METRIC_QUANTILE="0.95"
        VECTOR_SEARCH_P95=$(echo "$metrics" | histogram_quantile_from_metrics)
      fi
      if [[ "$VECTOR_SEARCH_P95" != "nan" && -n "$VECTOR_SEARCH_P95" ]]; then
        assert_less_than "$VECTOR_SEARCH_P95" "$SEARCH_LATENCY_THRESHOLD" "Vector search p95 under threshold" || rc=1
      else
        warn "Vector search histogram missing"
      fi
      ;;
    backup_script_exists)
      assert_file_exists "backups/backup.sh" "Backup script present" || rc=1
      ;;
    backup_run)
      run_backup_job || rc=1
      assert_not_empty "$LATEST_BACKUP_TS" "Backup timestamp recorded" || rc=1
      ;;
    backup_postgres_artifact)
      discover_latest_backup
      local file="$BACKUP_ROOT/postgres/backup-$LATEST_BACKUP_TS.dump"
      assert_file_exists "$file" "Postgres dump created" || rc=1
      ;;
    backup_qdrant_snapshot)
      discover_latest_backup
      local file="$BACKUP_ROOT/qdrant/snapshot-$LATEST_BACKUP_TS.tar.gz"
      assert_file_exists "$file" "Qdrant snapshot created" || rc=1
      ;;
    backup_files_archived)
      discover_latest_backup
      local vault="$BACKUP_ROOT/files/vault-$LATEST_BACKUP_TS.tar.gz"
      local uploads="$BACKUP_ROOT/files/uploads-$LATEST_BACKUP_TS.tar.gz"
      assert_file_exists "$vault" "Vault archive present" || rc=1
      assert_file_exists "$uploads" "Uploads archive present" || rc=1
      ;;
    backup_manifest)
      discover_latest_backup
      local manifest="$BACKUP_ROOT/manifest-$LATEST_BACKUP_TS.txt"
      assert_file_exists "$manifest" "Backup manifest present" || rc=1
      assert_contains "$(head -n 5 "$manifest")" "$LATEST_BACKUP_TS" "Manifest references timestamp" || rc=1
      ;;
    restore_script_exists)
      assert_file_exists "backups/restore.sh" "Restore script present" || rc=1
      ;;
    restore_temp_db)
      discover_latest_backup
      trap cleanup_restore_db EXIT
      stage4_restore_temp_db "$LATEST_BACKUP_TS" || rc=1
      local exists
      exists=$(docker exec vib-postgres psql -U "${POSTGRES_USER:-vib}" -d postgres -t -c "SELECT COUNT(*) FROM pg_database WHERE datname = '$RESTORE_DB_NAME';" | tr -d '[:space:]')
      assert_equals "$exists" "1" "Temp database restored" || rc=1
      cleanup_restore_db
      trap - EXIT
      ;;
    retention_scheduler)
      docker exec vib-beat pgrep -f "celery" >/dev/null 2>&1 || rc=1
      if [[ $rc -eq 0 ]]; then
        success "Celery beat running"
      else
        error "Celery beat not running"
      fi
      ;;
    retention_cleanup_manual)
      local output
      # Task can exit non-zero when no eligible rows exist; capture output but don't fail immediately.
      output=$(docker exec vib-worker celery -A worker.tasks call worker.tasks.cleanup_old_data 2>&1 || true)
      assert_contains "$output" "SUCCESS" "Retention cleanup task invoked" || rc=1
      ;;
    retention_metrics)
      local value
      value=$(metric_value "retention_cleanup_total" || echo 0)
      assert_greater_than "${value:-0}" "0" "Retention cleanup metric reports work" || rc=1
      ;;
    database_size_report)
      local output
      output=$(bash scripts/check-db-size.sh 2>&1 || true)
      assert_contains "$output" "VIB Database Size Report" "DB size script runs" || rc=1
      ;;
    database_vacuum)
      docker exec vib-postgres psql -U "${POSTGRES_USER:-vib}" -d "${POSTGRES_DB:-vib}" -c "VACUUM (ANALYZE) notes;" >/dev/null 2>&1 || rc=1
      [[ $rc -eq 0 ]] && success "VACUUM completed"
      ;;
    metrics_prometheus_format)
      local content
      content=$(fetch_metrics_payload | head -n 1)
      assert_contains "$content" "# HELP" "Metrics endpoint in Prometheus format" || rc=1
      ;;
    backup_manifest_counts)
      discover_latest_backup
      local manifest="$BACKUP_ROOT/manifest-$LATEST_BACKUP_TS.txt"
      local counts
      counts=$(grep -Fc "Postgres" "$manifest" || true)
      assert_greater_than "${counts:-0}" "0" "Manifest lists artifacts" || rc=1
      ;;
    *)
      error "Unknown Stage4 check $check"
      rc=1
      ;;
  esac
  return $rc
}

run_stage4() {
  section "STAGE 4: BACKUPS + RETENTION + OBSERVABILITY"
  require_env_vars METRICS_URL BASE_URL TOKEN BACKUP_ROOT REMINDER_FIRE_LAG_TARGET PUSH_SUCCESS_TARGET DOC_INGESTION_TARGET SEARCH_LATENCY_THRESHOLD
  local tests=(
    "stage4_metrics_defined stage4_check metrics_defined"
    "stage4_metrics_non_zero stage4_check metrics_non_zero"
    "stage4_metrics_histograms stage4_check metrics_histograms"
    "stage4_metrics_gauges stage4_check metrics_gauges"
    "stage4_metrics_counters stage4_check metrics_counters"
    "stage4_slo_reminder stage4_check slo_reminder_fire_lag"
    "stage4_slo_push stage4_check slo_push_success"
    "stage4_slo_document stage4_check slo_document_ingestion"
    "stage4_slo_vector stage4_check slo_vector_search"
    "stage4_backup_script stage4_check backup_script_exists"
    "stage4_backup_run stage4_check backup_run"
    "stage4_backup_postgres stage4_check backup_postgres_artifact"
    "stage4_backup_qdrant stage4_check backup_qdrant_snapshot"
    "stage4_backup_files stage4_check backup_files_archived"
    "stage4_backup_manifest stage4_check backup_manifest"
    "stage4_restore_script stage4_check restore_script_exists"
    "stage4_restore_temp_db stage4_check restore_temp_db"
    "stage4_retention_scheduler stage4_check retention_scheduler"
    "stage4_retention_cleanup stage4_check retention_cleanup_manual"
    "stage4_retention_metrics stage4_check retention_metrics"
    "stage4_db_size stage4_check database_size_report"
    "stage4_db_vacuum stage4_check database_vacuum"
    "stage4_metrics_prom stage4_check metrics_prometheus_format"
    "stage4_manifest_counts stage4_check backup_manifest_counts"
  )
  for entry in "${tests[@]}"; do
    IFS=' ' read -r name func arg <<<"$entry"
    run_test "$name" "$func" "$arg"
  done
}
