#!/usr/bin/env bash
# Performance Tests
# Tests API latency, search performance, and concurrent request handling
#
# Environment variables leveraged here:
#   - BASE_URL: API server root (default http://localhost:8000)
#   - TOKEN / API_TOKEN: bearer token for authenticated requests
#   - API_LATENCY_THRESHOLD: max acceptable /api/v1/health latency (ms)
#   - SEARCH_LATENCY_THRESHOLD: max acceptable /api/v1/search latency (ms)
#   - DOC_INGESTION_TARGET: max acceptable ingestion duration (seconds)
#   - CONCURRENT_REQUEST_THRESHOLD: tolerated failures in burst health checks
#   - DOC_JOB_WAIT_TIMEOUT: optional override for job duration polling timeout
#   - DOC_JOB_POLL_INTERVAL: optional override for job duration polling interval

set -euo pipefail

LATENCY_SAMPLES=${LATENCY_SAMPLES:-10}
CURL_BURST_SIZE=${CURL_BURST_SIZE:-10}
DOC_JOB_WAIT_TIMEOUT=${DOC_JOB_WAIT_TIMEOUT:-300}
DOC_JOB_POLL_INTERVAL=${DOC_JOB_POLL_INTERVAL:-5}

poll_document_job_duration() {
  local job_id="$1"
  local timeout="$2"
  local interval="$3"
  local waited=0
  while [[ $waited -lt $timeout ]]; do
    local duration
    duration=$(psql_query "SELECT EXTRACT(EPOCH FROM (completed_at - started_at)) FROM jobs WHERE id = '$job_id' AND completed_at IS NOT NULL;" || true)
    duration=$(echo "$duration" | tr -d '[:space:]')
    if [[ -n "$duration" ]]; then
      echo "$duration"
      return 0
    fi
    sleep "$interval"
    waited=$((waited + interval))
  done
  return 1
}

wait_for_document_job_duration() {
  local job_id="$1"
  local timeout="$2"
  local interval="$3"
  local duration
  if [[ -z "$job_id" || "$job_id" == "null" ]]; then
    error "Document job id unavailable for ingestion timing"
    return 1
  fi
  if ! duration=$(poll_document_job_duration "$job_id" "$timeout" "$interval"); then
    error "Timed out waiting for job $job_id to report completed_at"
    return 1
  fi
  echo "$duration"
  return 0
}

performance_check() {
  local check="$1"
  local rc=0
  case "$check" in
    api_latency)
      local latency
      latency=$(measure_latency "/api/v1/health" "$LATENCY_SAMPLES")
      log "api_latency_ms=$latency threshold_ms=$API_LATENCY_THRESHOLD"
      assert_less_than "$latency" "$API_LATENCY_THRESHOLD" "Health endpoint latency <$API_LATENCY_THRESHOLD ms" || rc=1
      ;;
    search_performance)
      local latency
      latency=$(measure_latency "/api/v1/search?q=knowledge" "$LATENCY_SAMPLES")
      log "search_latency_ms=$latency threshold_ms=$SEARCH_LATENCY_THRESHOLD"
      assert_less_than "$latency" "$SEARCH_LATENCY_THRESHOLD" "Search latency <$SEARCH_LATENCY_THRESHOLD ms" || rc=1
      ;;
    document_processing_speed)
      ensure_twenty_page_document
      local duration
      if duration=$(wait_for_document_job_duration "$DOC_TWENTY_JOB_ID" "$DOC_JOB_WAIT_TIMEOUT" "$DOC_JOB_POLL_INTERVAL"); then
        log "doc_ingestion_duration_s=$duration target_s=$DOC_INGESTION_TARGET"
        assert_less_than "$duration" "$DOC_INGESTION_TARGET" "Document ingestion meets SLO" || rc=1
      else
        rc=1
      fi
      ;;
    concurrent_requests)
      local failures=0
      local pids=()
      for ((i = 0; i < CURL_BURST_SIZE; i++)); do
        (
          curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/health" | grep -q "200"
        ) &
        pids+=($!)
      done
      for pid in "${pids[@]}"; do
        if ! wait "$pid"; then
          failures=$((failures + 1))
        fi
      done
      local allowed_failures=${CONCURRENT_REQUEST_THRESHOLD:-0}
      log "concurrent_health_checks=${CURL_BURST_SIZE} failures=$failures allowed_failures=$allowed_failures"
      assert_less_than "$failures" "$((allowed_failures + 1))" "Burst of health checks succeed (<=${allowed_failures} failures)" || rc=1
      ;;
    *)
      error "Unknown performance check $check"
      rc=1
      ;;
  esac
  return $rc
}

run_performance_tests() {
  section "PERFORMANCE TESTS"
  local tests=(
    "perf_api_latency performance_check api_latency"
    "perf_search performance_check search_performance"
    "perf_doc_processing performance_check document_processing_speed"
    "perf_concurrent_requests performance_check concurrent_requests"
  )
  for entry in "${tests[@]}"; do
    IFS=' ' read -r name func arg <<<"$entry"
    run_test "$name" "$func" "$arg"
  done
}
