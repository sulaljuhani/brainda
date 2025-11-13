#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE="$REPO_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing .env file at $ENV_FILE" >&2
    exit 1
fi

if ! TOKEN=$(grep -E '^API_TOKEN=' "$ENV_FILE" | cut -d= -f2-); then
    echo "API_TOKEN not found in $ENV_FILE" >&2
    exit 1
fi

if [[ -z "$TOKEN" ]]; then
    echo "API_TOKEN is empty in $ENV_FILE" >&2
    exit 1
fi

BASE_URL="http://localhost:8003"

echo "======================================"
echo "Stage 2 Validation Test"
echo "======================================"
echo ""

# Helper functions
log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

extract_metric() {
    local metric_name="$1"
    awk -v metric="$metric_name" '$1 == metric {print $2; exit}'
}

metric_increased() {
    local current="$1"
    local baseline="$2"
    if [[ -z "$current" || -z "$baseline" ]]; then
        return 1
    fi
    awk -v current="$current" -v baseline="$baseline" 'BEGIN {exit !((current + 0) > (baseline + 0))}'
}

cleanup() {
    set +e
    if [[ -n "${REMINDER_ID:-}" ]]; then
        curl -s -X DELETE "$BASE_URL/api/v1/reminders/$REMINDER_ID" \
          -H "Authorization: Bearer $TOKEN" >/dev/null
    fi
    if [[ -n "${RECURRING_ID:-}" ]]; then
        curl -s -X DELETE "$BASE_URL/api/v1/reminders/$RECURRING_ID" \
          -H "Authorization: Bearer $TOKEN" >/dev/null
    fi
    if [[ -n "${DEVICE_ID:-}" ]]; then
        curl -s -X POST "$BASE_URL/api/v1/devices/$DEVICE_ID/unregister" \
          -H "Authorization: Bearer $TOKEN" \
          -H "Content-Type: application/json" \
          -d '{}' >/dev/null
    fi
    docker exec vib-postgres psql -U vib -d vib -c "DELETE FROM reminders WHERE title = 'DB-level test';" >/dev/null 2>&1
    set -e
}

trap cleanup EXIT

# Test 1: Create simple reminder (2 minutes from now)
log "Test 1: Creating simple reminder (2 min from now)..."
NOW_PLUS_2=$(python3 - <<'PY'
from datetime import datetime, timedelta, timezone
future = datetime.now(timezone.utc) + timedelta(minutes=2)
print(future.strftime("%Y-%m-%dT%H:%M:00Z"))
PY
)
LOCAL_TIME=$(python3 - <<'PY'
from datetime import datetime, timedelta
future_local = datetime.now() + timedelta(minutes=2)
print(future_local.strftime("%H:%M:00"))
PY
)

RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/reminders" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"Stage 2 Test Reminder\",
    \"body\": \"This is a test\",
    \"due_at_utc\": \"$NOW_PLUS_2\",
    \"due_at_local\": \"$LOCAL_TIME\",
    \"timezone\": \"UTC\"
  }")

REMINDER_ID=$(jq -r '.data.id' <<<"$RESPONSE")

if [[ "$REMINDER_ID" == "null" || -z "$REMINDER_ID" ]]; then
    log "✗ Failed to create reminder"
    printf 'Response: %s\n' "$RESPONSE"
    exit 1
fi

log "✓ Reminder created: $REMINDER_ID"
echo ""

# Test 2: Verify deduplication
log "Test 2: Testing deduplication (create same reminder)..."
sleep 2
RESPONSE2=$(curl -s -X POST "$BASE_URL/api/v1/reminders" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"Stage 2 Test Reminder\",
    \"body\": \"This is a test\",
    \"due_at_utc\": \"$NOW_PLUS_2\",
    \"due_at_local\": \"$LOCAL_TIME\",
    \"timezone\": \"UTC\"
  }")

REMINDER_ID2=$(jq -r '.data.id' <<<"$RESPONSE2")
IS_DEDUPED=$(jq -r '.deduplicated' <<<"$RESPONSE2")

if [[ "$REMINDER_ID" != "$REMINDER_ID2" ]]; then
    log "✗ Deduplication failed (got different IDs)"
    exit 1
fi

if [[ "$IS_DEDUPED" != "true" ]]; then
    log "✗ Deduplication not flagged correctly"
    exit 1
fi

log "✓ Deduplication working (same ID returned)"
echo ""

# Test 3: List reminders
log "Test 3: Listing reminders..."
REMINDERS=$(curl -s "$BASE_URL/api/v1/reminders" \
  -H "Authorization: Bearer $TOKEN")

COUNT=$(jq 'length' <<<"$REMINDERS")
log "✓ Found $COUNT reminder(s)"
echo ""

# Test 4: Create recurring reminder
log "Test 4: Creating recurring reminder (weekly)..."
NEXT_MONDAY=$(date -u -d 'next monday 09:00' '+%Y-%m-%dT09:00:00Z')

RECURRING_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/reminders" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"Weekly Test Reminder\",
    \"due_at_utc\": \"$NEXT_MONDAY\",
    \"due_at_local\": \"09:00:00\",
    \"timezone\": \"UTC\",
    \"repeat_rrule\": \"FREQ=WEEKLY;BYDAY=MO\"
  }")

RECURRING_ID=$(jq -r '.data.id' <<<"$RECURRING_RESPONSE")

if [[ "$RECURRING_ID" == "null" || -z "$RECURRING_ID" ]]; then
    log "✗ Failed to create recurring reminder"
    printf 'Response: %s\n' "$RECURRING_RESPONSE"
    exit 1
fi

log "✓ Recurring reminder created: $RECURRING_ID"
echo ""

# Test 5: Snooze reminder
log "Test 5: Testing snooze..."
SNOOZE_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/reminders/$REMINDER_ID/snooze" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"duration_minutes": 15}')

SNOOZE_SUCCESS=$(jq -r '.success' <<<"$SNOOZE_RESPONSE")

if [[ "$SNOOZE_SUCCESS" != "true" ]]; then
    log "✗ Snooze failed"
    printf 'Response: %s\n' "$SNOOZE_RESPONSE"
    exit 1
fi

log "✓ Reminder snoozed successfully"
echo ""

# Test 6: Check database dedup constraint
log "Test 6: Testing database constraint (attempt to bypass service layer)..."
docker exec vib-postgres psql -U vib -d vib -c "
    INSERT INTO reminders (user_id, title, due_at_utc, due_at_local, timezone)
    SELECT id, 'DB-level test', NOW() + INTERVAL '1 day', '12:00:00', 'UTC' FROM users LIMIT 1;
"
log "✓ DB insert OK"
log "Attempting duplicate..."
if docker exec vib-postgres psql -U vib -d vib -c "
    INSERT INTO reminders (user_id, title, due_at_utc, due_at_local, timezone)
    SELECT id, 'DB-level test', NOW() + INTERVAL '1 day', '12:00:00', 'UTC' FROM users LIMIT 1;
"; then
    log "✗ Duplicate insert unexpectedly succeeded"
    exit 1
fi
log "✓ DB duplicate failed as expected"
echo ""

# Test 7: Register a device
log "Test 7: Registering a device for push notifications..."
DEVICE_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/devices/register" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"platform": "web", "push_token": "test-token:12345", "push_endpoint": "http://test.com"}')

DEVICE_ID=$(jq -r '.device_id' <<<"$DEVICE_RESPONSE")
if [[ "$DEVICE_ID" == "null" || -z "$DEVICE_ID" ]]; then
    log "✗ Failed to register device"
    printf 'Response: %s\n' "$DEVICE_RESPONSE"
    exit 1
fi
log "✓ Device registered: $DEVICE_ID"
echo ""
WAIT_TIMEOUT=${WAIT_TIMEOUT:-120}
POLL_INTERVAL=${POLL_INTERVAL:-5}

log "Recording baseline metrics before wait..."
METRICS=$(curl -s "$BASE_URL/api/v1/metrics")
BASELINE_FIRED=$(extract_metric "reminders_fired_total" <<<"$METRICS")
BASELINE_FIRED=${BASELINE_FIRED:-0}

log "Waiting for reminder to fire (timeout: ${WAIT_TIMEOUT}s, interval: ${POLL_INTERVAL}s)..."
START_TIME=$(date +%s)
FIRE_CONFIRMED=false
while true; do
    CURRENT_METRICS=$(curl -s "$BASE_URL/api/v1/metrics" || true)
    if [[ -n "$CURRENT_METRICS" ]]; then
        CURRENT_FIRED=$(extract_metric "reminders_fired_total" <<<"$CURRENT_METRICS")
        CURRENT_FIRED=${CURRENT_FIRED:-0}
        if metric_increased "$CURRENT_FIRED" "$BASELINE_FIRED"; then
            log "✓ Reminder fired (count increased from $BASELINE_FIRED to $CURRENT_FIRED)"
            METRICS="$CURRENT_METRICS"
            FIRE_CONFIRMED=true
            break
        fi
    fi

    NOW=$(date +%s)
    if (( NOW - START_TIME >= WAIT_TIMEOUT )); then
        break
    fi
    sleep "$POLL_INTERVAL"
done

if [[ "$FIRE_CONFIRMED" != true ]]; then
    log "✗ Reminder did not fire before timeout"
    exit 1
fi

# Test 8: Check metrics
log "Test 8: Checking metrics for fired reminder..."

FIRED_COUNT=$(extract_metric "reminders_fired_total" <<<"$METRICS")
if [[ -z "$FIRED_COUNT" ]]; then
    log "✗ Fired reminder metric not found"
    exit 1
fi
log "✓ Fired reminder count: $FIRED_COUNT"

LAG_METRIC=$(printf '%s\n' "$METRICS" | grep "reminder_fire_lag_seconds_bucket" || true)
if [[ -z "$LAG_METRIC" ]]; then
    log "✗ Fire lag metric not found"
    exit 1
fi
log "✓ Fire lag metric present"

echo ""
log "--------------------------------------"
log "MANUAL VERIFICATION STEPS:"
echo " 1. Check orchestrator logs for 'reminder_firing' and 'notification_sent' messages"
echo " 2. Check notification_delivery table for a 'delivered' status"
echo " 3. Check metrics endpoint for 'push_delivery_success_total' and 'reminder_fire_lag'"
echo " 4. Test notification actions (Snooze, Done) from notification UI"
echo " 5. Verify Web Push service worker is registered in browser DevTools"
echo ""
log "Reminder ID for manual testing: $REMINDER_ID"
log "Device ID for manual testing: $DEVICE_ID"
echo ""
echo "======================================"
log "✅ Stage 2 validation complete!"
echo "======================================"
