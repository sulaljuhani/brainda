#!/usr/bin/env bash
set -euo pipefail

METRICS_URL=${METRICS_URL:-http://localhost:8000/api/v1/metrics}

fetch_metrics() {
  curl -sS "$METRICS_URL"
}

METRICS=$(fetch_metrics)

echo "======================================"
echo "Brainda SLO Dashboard"
echo "Source: $METRICS_URL"
echo "======================================"

# Reminder fire lag p95
if echo "$METRICS" | grep -q 'reminder_fire_lag_seconds_bucket'; then
  echo "Reminder Fire Lag (p95 target <5s):"
  echo "$METRICS" | grep 'reminder_fire_lag_seconds_bucket' | tail -n5
else
  echo "Reminder Fire Lag: no samples yet"
fi

echo ""
# Push delivery success rate
SUCCESSES=$(echo "$METRICS" | awk '/^push_delivery_success_total/{sum+=$2} END {printf "%.0f", sum}')
FAILURES=$(echo "$METRICS" | awk '/^push_delivery_failure_total/{sum+=$2} END {printf "%.0f", sum}')
TOTAL=$((SUCCESSES + FAILURES))
if [[ $TOTAL -gt 0 ]]; then
  RATE=$(awk -v s=$SUCCESSES -v t=$TOTAL 'BEGIN{printf "%.2f", (s/t)*100}')
  echo "Push Delivery Success Rate: $RATE% (target >98%)"
else
  echo "Push Delivery Success Rate: no data"
fi

echo ""
# Document ingestion time
if echo "$METRICS" | grep -q 'document_ingestion_duration_seconds_bucket'; then
  echo "Document Ingestion Duration buckets:"
  echo "$METRICS" | grep 'document_ingestion_duration_seconds_bucket' | tail -n5
else
  echo "Document Ingestion Duration: no samples"
fi

echo ""
# Vector search latency
if echo "$METRICS" | grep -q 'vector_search_duration_seconds_bucket'; then
  echo "Vector Search Duration buckets:"
  echo "$METRICS" | grep 'vector_search_duration_seconds_bucket' | tail -n5
else
  echo "Vector Search Duration: no samples"
fi

echo ""
# System health gauges
echo "System Health Gauges:"
for metric in celery_queue_depth postgres_connections redis_memory_bytes; do
  matches=$(echo "$METRICS" | grep "^$metric" || true)
  if [[ -n "$matches" ]]; then
    echo "$matches"
  else
    echo "$metric: no samples"
  fi
done

echo "======================================"
