#!/usr/bin/env bash
set -euo pipefail

if ! command -v curl >/dev/null 2>&1; then
  echo "✗ curl is required but not installed" >&2
  exit 2
fi

METRICS_URL=${METRICS_URL:-http://localhost:8000/api/v1/metrics}
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

tmpfile=$(mktemp)
cleanup() {
  rm -f "$tmpfile"
}
trap cleanup EXIT

echo "Fetching metrics from: $METRICS_URL"

http_status=""
if ! http_status=$(curl -sS -o "$tmpfile" -w '%{http_code}' "$METRICS_URL"); then
  echo "✗ Failed to reach metrics endpoint: $METRICS_URL" >&2
  exit 2
fi

if [[ ! $http_status =~ ^[0-9]{3}$ ]]; then
  echo "✗ Unexpected HTTP status from metrics endpoint: $http_status" >&2
  exit 2
fi

if (( http_status < 200 || http_status >= 300 )); then
  echo "✗ Metrics endpoint $METRICS_URL returned HTTP $http_status" >&2
  echo "--- Response body ---" >&2
  cat "$tmpfile" >&2
  exit 2
fi

OUTPUT=$(<"$tmpfile")

missing=0
for metric in "${REQUIRED_METRICS[@]}"; do
  if ! echo "$OUTPUT" | grep -q "^# HELP $metric"; then
    echo "✗ Missing HELP for $metric"
    missing=$((missing + 1))
    continue
  fi

  if echo "$OUTPUT" | grep -Eq "^${metric}($|\{|\s)"; then
    echo "✓ $metric"
  else
    echo "✗ No samples for $metric"
    missing=$((missing + 1))
  fi
done

if [[ $missing -gt 0 ]]; then
  echo ""
  echo "✗ $missing metric checks failed"
  exit 1
fi

echo ""
echo "✓ All required metrics exposed"
