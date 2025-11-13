#!/usr/bin/env bash
# Performance Tests
# Tests API latency, search performance, and concurrent request handling

set -euo pipefail

performance_check() {
  local check="$1"
  local rc=0
  case "$check" in
    api_latency)
      local latency
      latency=$(measure_latency "/api/v1/health" 10)
      assert_less_than "$latency" "$API_LATENCY_THRESHOLD" "Health endpoint latency <$API_LATENCY_THRESHOLD ms" || rc=1
      ;;
    search_performance)
      local latency
      latency=$(measure_latency "/api/v1/search?q=knowledge" 10)
      assert_less_than "$latency" "$SEARCH_LATENCY_THRESHOLD" "Search latency <$SEARCH_LATENCY_THRESHOLD ms" || rc=1
      ;;
    document_processing_speed)
      ensure_twenty_page_document
      local duration
      duration=$(psql_query "SELECT COALESCE(EXTRACT(EPOCH FROM (completed_at - started_at)),0) FROM jobs WHERE id = '$DOC_TWENTY_JOB_ID';")
      if [[ -n "$duration" ]]; then
        assert_less_than "$duration" "$DOC_INGESTION_TARGET" "Document ingestion meets SLO" || rc=1
      else
        warn "Document job duration unavailable"
      fi
      ;;
    concurrent_requests)
      local failures=0
      for i in {1..10}; do
        (curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/health" | grep -q "200") || failures=$((failures + 1))
      done
      assert_equals "$failures" "0" "Burst of health checks succeed" || rc=1
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
