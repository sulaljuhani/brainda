#!/usr/bin/env bash
set -euo pipefail

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

missing=0
OUTPUT=$(curl -sS "$METRICS_URL")

for metric in "${REQUIRED_METRICS[@]}"; do
  if echo "$OUTPUT" | grep -q "^# HELP $metric"; then
    echo "✓ $metric"
  else
    echo "✗ Missing $metric"
    missing=$((missing + 1))
  fi
done

if [[ $missing -gt 0 ]]; then
  echo ""
  echo "✗ $missing metrics missing"
  exit 1
fi

echo ""
echo "✓ All required metrics exposed"
