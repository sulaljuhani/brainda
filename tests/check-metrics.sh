#!/usr/bin/env bash
set -euo pipefail

# Enable debug mode with DEBUG=1
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

# Dependency check with clear error message
if ! command -v curl >/dev/null 2>&1; then
  echo "✗ curl is required but not installed" >&2
  echo "  Install with: apt-get install curl (Debian/Ubuntu) or yum install curl (RHEL/CentOS)" >&2
  exit 2
fi

# Configuration with validation
METRICS_URL=${METRICS_URL:-http://localhost:8000/api/v1/metrics}
TIMEOUT=${METRICS_TIMEOUT:-30}
VERBOSE=${VERBOSE:-0}

# Validate METRICS_URL format
if [[ ! "$METRICS_URL" =~ ^https?:// ]]; then
  echo "✗ Invalid METRICS_URL format: $METRICS_URL" >&2
  echo "  Must start with http:// or https://" >&2
  exit 2
fi

REQUIRED_METRICS=(
  reminder_fire_lag_seconds
  push_delivery_success_total
  push_delivery_failure_total
  chat_turns_total
  tool_calls_total
  reminders_fired_total
  document_ingestion_duration_seconds
  vector_search_duration_seconds
  celery_queue_depth
  postgres_connections
  redis_memory_bytes
)

# Create temp file with automatic cleanup
tmpfile=$(mktemp) || {
  echo "✗ Failed to create temporary file" >&2
  exit 2
}
cleanup() {
  local exit_code=$?
  rm -f "$tmpfile"
  if [[ "${DEBUG:-0}" == "1" ]]; then
    echo "[DEBUG] Cleanup complete, exit code: $exit_code" >&2
  fi
  exit $exit_code
}
trap cleanup EXIT INT TERM

# Verbose logging helper
log_verbose() {
  if [[ "$VERBOSE" == "1" ]]; then
    echo "[VERBOSE] $*" >&2
  fi
}

log_verbose "Fetching metrics from: $METRICS_URL (timeout: ${TIMEOUT}s)"
echo "Fetching metrics from: $METRICS_URL"

# Fetch metrics with timeout and better error handling
http_status=""
if ! http_status=$(curl -sS --max-time "$TIMEOUT" -o "$tmpfile" -w '%{http_code}' "$METRICS_URL" 2>&1); then
  echo "✗ Failed to reach metrics endpoint: $METRICS_URL" >&2
  echo "  Error: $http_status" >&2
  exit 2
fi

# Validate HTTP status format
if [[ ! $http_status =~ ^[0-9]{3}$ ]]; then
  echo "✗ Unexpected HTTP status from metrics endpoint: $http_status" >&2
  exit 2
fi

# Check HTTP status code
if (( http_status < 200 || http_status >= 300 )); then
  echo "✗ Metrics endpoint $METRICS_URL returned HTTP $http_status" >&2
  echo "--- Response body ---" >&2
  head -n 50 "$tmpfile" >&2
  exit 2
fi

log_verbose "Successfully fetched metrics (HTTP $http_status)"

# Validate temp file is not empty
if [[ ! -s "$tmpfile" ]]; then
  echo "✗ Metrics response is empty" >&2
  exit 2
fi

OUTPUT=$(<"$tmpfile")

# Track missing metrics
missing=0
declare -a missing_metrics=()
declare -a found_metrics=()

for metric in "${REQUIRED_METRICS[@]}"; do
  log_verbose "Checking metric: $metric"

  # Check for HELP line
  if ! echo "$OUTPUT" | grep -q "^# HELP $metric"; then
    echo "✗ Missing HELP for $metric"
    missing=$((missing + 1))
    missing_metrics+=("$metric (no HELP)")
    continue
  fi

  # Check for actual metric samples
  if echo "$OUTPUT" | grep -Eq "^${metric}($|\{|\s)"; then
    echo "✓ $metric"
    found_metrics+=("$metric")
  else
    echo "✗ No samples for $metric"
    missing=$((missing + 1))
    missing_metrics+=("$metric (no samples)")
  fi
done

# Summary
echo ""
echo "============================================"
echo "Metrics Check Summary"
echo "============================================"
echo "Total metrics checked: ${#REQUIRED_METRICS[@]}"
echo "Found: ${#found_metrics[@]}"
echo "Missing: $missing"

if [[ $missing -gt 0 ]]; then
  echo ""
  echo "Missing metrics:"
  for m in "${missing_metrics[@]}"; do
    echo "  - $m"
  done
  echo ""
  echo "✗ $missing metric checks failed"
  exit 1
fi

echo ""
echo "✓ All required metrics exposed"
exit 0
