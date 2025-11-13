#!/usr/bin/env bash
# stage_runner.sh
# Main test runner that orchestrates all VIB integration tests
# Sources common functions and stage-specific tests

set -euo pipefail
IFS=$'\n\t'

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_ROOT"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
START_TIME="$(date +%s)"
TEST_DIR="${TEST_DIR:-/tmp/vib-test-$TIMESTAMP}"
mkdir -p "$TEST_DIR"
TEST_LOG="$TEST_DIR/run.log"
touch "$TEST_LOG"
exec > >(tee -a "$TEST_LOG") 2>&1

# These will be used by common.sh
export SCRIPT_ROOT TIMESTAMP START_TIME TEST_DIR TEST_LOG

# Default values for variables used by common.sh
BASE_URL="${BASE_URL:-http://localhost:8000}"
RUN_STAGE=""
FAST_MODE=false
HTML_REPORT=false
VERBOSE=false

usage() {
  cat <<USAGE
Usage: $0 [options]
  --stage N         Run only Stage N tests (0-8, performance, workflows)
                      0: Infrastructure
                      1: Notes + Vector Search
                      2: Reminders + Notifications
                      3: Documents + RAG
                      4: Backups + Retention + Observability
                      5: Mobile + Idempotency
                      6: Calendar + RRULE
                      7: Google Calendar Sync
                      8: Passkeys + Multi-user
                      performance: Performance tests
                      workflows: End-to-end workflows
  --fast            Skip slow tests (reminder firing, long-running DOC/RAG)
  --html-report     Generate HTML report in test directory
  --verbose         Enable verbose curl output
  --help            Show this message

Examples:
  $0                              # Run all tests
  $0 --stage 5                    # Run only Stage 5 (Idempotency) tests
  $0 --stage 6 --verbose          # Run Stage 6 (Calendar) with verbose output
  $0 --fast --html-report         # Run all tests (skip slow ones), generate HTML report
USAGE
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --stage)
      RUN_STAGE="$2"
      shift 2
      ;;
    --fast)
      FAST_MODE=true
      shift
      ;;
    --html-report)
      HTML_REPORT=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

# Export variables for sourced scripts
export BASE_URL RUN_STAGE FAST_MODE HTML_REPORT VERBOSE

# Source common functions and fixtures
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Source all stage test files
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/stage0.sh"
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/stage1.sh"
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/stage2.sh"
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/stage3.sh"
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/stage4.sh"
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/stage5.sh"
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/stage6.sh"
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/stage7.sh"
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/stage8.sh"
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/performance.sh"
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/workflows.sh"

print_summary() {
  local end_time duration
  end_time=$(date +%s)
  duration=$((end_time - START_TIME))
  section "TEST SUMMARY"
  echo "Total Tests: $TOTAL_TESTS"
  echo "Passed: $PASSED_TESTS"
  echo "Failed: $FAILED_TESTS"
  echo "Warnings: $WARNINGS"
  printf 'Duration: %dm %ds\n' $((duration/60)) $((duration%60))
  if [[ $TOTAL_TESTS -gt 0 ]]; then
    local rate
    rate=$(awk -v p="$PASSED_TESTS" -v t="$TOTAL_TESTS" 'BEGIN{if(t==0){print "0.0"}else{printf "%.1f", (p/t)*100}}')
    echo "Pass Rate: $rate%"
  fi
  if [[ $FAILED_TESTS -gt 0 ]]; then
    echo ""
    echo "Failed Tests:"
    for name in "${FAILED_TEST_NAMES[@]}"; do
      echo "  - $name"
    done
  fi
  echo ""
  echo "SLO Status:"
  if [[ -n "$REMINDER_FIRE_LAG_P95" && "$REMINDER_FIRE_LAG_P95" != "unknown" ]]; then
    echo "  - Reminder fire lag p95: ${REMINDER_FIRE_LAG_P95}s (target < ${REMINDER_FIRE_LAG_TARGET}s)"
  else
    echo "  - Reminder fire lag p95: unavailable"
  fi
  if [[ -n "$PUSH_SUCCESS_RATE" && "$PUSH_SUCCESS_RATE" != "unknown" ]]; then
    local display_rate target_rate
    display_rate=$(awk -v r="$PUSH_SUCCESS_RATE" 'BEGIN{printf "%.2f%%", r*100}')
    target_rate=$(awk -v t="$PUSH_SUCCESS_TARGET" 'BEGIN{printf "%.0f%%", t*100}')
    echo "  - Push success rate: $display_rate (target > $target_rate)"
  else
    echo "  - Push success rate: unavailable"
  fi
  if [[ -n "$DOC_INGESTION_P95" && "$DOC_INGESTION_P95" != "unknown" ]]; then
    echo "  - Document ingestion p95: ${DOC_INGESTION_P95}s (target < ${DOC_INGESTION_TARGET}s)"
  else
    echo "  - Document ingestion p95: unavailable"
  fi
  if [[ -n "$VECTOR_SEARCH_P95" && "$VECTOR_SEARCH_P95" != "unknown" ]]; then
    echo "  - Vector search p95: ${VECTOR_SEARCH_P95}ms (target < ${SEARCH_LATENCY_THRESHOLD}ms)"
  else
    echo "  - Vector search p95: unavailable"
  fi
  echo ""
  echo "Logs: $TEST_LOG"
  echo "Artifacts: $TEST_DIR"
}

generate_json_report() {
  local report="$TEST_DIR/results.json"
  local duration=$(( $(date +%s) - START_TIME ))
  jq -n \
    --arg timestamp "$TIMESTAMP" \
    --arg base_url "$BASE_URL" \
    --arg duration "$duration" \
    --argjson total "$TOTAL_TESTS" \
    --argjson passed "$PASSED_TESTS" \
    --argjson failed "$FAILED_TESTS" \
    --argjson warnings "$WARNINGS" \
    --arg reminder_p95 "${REMINDER_FIRE_LAG_P95:-"null"}" \
    --arg push_rate "${PUSH_SUCCESS_RATE:-"null"}" \
    --arg doc_p95 "${DOC_INGESTION_P95:-"null"}" \
    --arg search_p95 "${VECTOR_SEARCH_P95:-"null"}" \
    --arg tests "$(printf '%s\n' "${TEST_RECORDS[@]}" | jq -Rsn '[inputs | select(length>0) | split("|") | {name:.[0], status:.[1], duration:.[2], message:.[3]}]')" \
    '($tests | fromjson) as $items | {
      timestamp: $timestamp,
      base_url: $base_url,
      duration_seconds: ($duration|tonumber),
      totals: {total: $total, passed: $passed, failed: $failed, warnings: $warnings},
      slo: {reminder_fire_lag_p95: ($reminder_p95|tonumber?), push_success_rate: ($push_rate|tonumber?), document_ingestion_p95: ($doc_p95|tonumber?), vector_search_p95: ($search_p95|tonumber?)},
      tests: $items
    }' > "$report"
  log "JSON report: $report"
}

generate_html_report() {
  local report="$TEST_DIR/report.html"
  cat > "$report" <<HTML
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>VIB MVP Test Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    .pass { color: #2d7f2d; }
    .fail { color: #c0392b; }
    .warn { color: #c78500; }
    table { border-collapse: collapse; width: 100%; margin-top: 16px; }
    th, td { border: 1px solid #ddd; padding: 8px; }
    th { background: #333; color: #fff; }
  </style>
</head>
<body>
  <h1>VIB MVP Test Report</h1>
  <p><strong>Timestamp:</strong> $TIMESTAMP</p>
  <p><strong>Base URL:</strong> $BASE_URL</p>
  <p><strong>Total:</strong> $TOTAL_TESTS &nbsp; <span class="pass">Passed: $PASSED_TESTS</span> &nbsp; <span class="fail">Failed: $FAILED_TESTS</span> &nbsp; <span class="warn">Warnings: $WARNINGS</span></p>
  <table>
    <tr><th>Test Name</th><th>Status</th><th>Duration</th><th>Message</th></tr>
HTML
  for record in "${TEST_RECORDS[@]}"; do
    IFS='|' read -r name status duration message <<<"$record"
    [[ -z "$name" ]] && continue
    local class="pass"
    [[ "$status" == "FAIL" ]] && class="fail"
    [[ "$status" == "SKIPPED" ]] && class="warn"
    cat >> "$report" <<ROW
    <tr class="$class"><td>${name}</td><td>${status}</td><td>${duration}</td><td>${message}</td></tr>
ROW
  done
  cat >> "$report" <<HTML
  </table>
</body>
</html>
HTML
  log "HTML report: $report"
}

main() {
  setup
  trap cleanup_test_data EXIT

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "0" ]]; then
    run_stage0
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "1" ]]; then
    run_stage1
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "2" ]]; then
    run_stage2
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "3" ]]; then
    run_stage3
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "4" ]]; then
    run_stage4
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "5" ]]; then
    run_stage5
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "6" ]]; then
    run_stage6
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "7" ]]; then
    run_stage7
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "8" ]]; then
    run_stage8
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "performance" ]]; then
    run_performance_tests
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "workflows" ]]; then
    run_workflow_tests
  fi

  cleanup_test_data
  print_summary
  generate_json_report
  if $HTML_REPORT; then
    generate_html_report
  fi

  if [[ $FAILED_TESTS -gt 0 ]]; then
    exit 1
  fi
}

main "$@"
