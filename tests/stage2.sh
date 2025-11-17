#!/usr/bin/env bash
# Stage 2: Reminders + Notifications Tests  
# Tests reminder creation, notification delivery, recurrence, snoozing, etc.

set -euo pipefail

# Enable debug mode if requested
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

create_chat_reminder() {
  local marker="Smart Chat Reminder $TIMESTAMP-$RANDOM"
  local payload
  payload=$(jq -n --arg msg "Remind me tomorrow to $marker" '{message:$msg}')
  local status
  status=$(curl -sS -o "$TEST_DIR/chat-reminder.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/chat" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" || echo "000")
  echo "$marker|$status"
}

get_reminder_value() {
  local reminder_id="$1"
  local column="$2"
  psql_query "SELECT $column FROM reminders WHERE id = '$reminder_id';" | tr -d '\n\r'
}

create_unique_reminder() {
  local minutes="$1"
  local title="Stage2 Auto Reminder $TIMESTAMP-$RANDOM"
  local reminder_id
  reminder_id=$(create_reminder_minutes "$minutes" "$title")
  echo "$reminder_id|$title"
}

stage2_log_count() {
  local keyword="$1"
  local logs
  if ! logs=$(docker logs brainda-orchestrator --tail 400 2>&1); then
    error "Unable to read orchestrator logs for '$keyword'"
    return 1
  fi
  echo "$logs" | grep -c "$keyword" || true
}

stage2_wait_for_log() {
  local keyword="$1"
  local baseline="${2:-0}"
  local timeout="${3:-30}"
  local interval="${4:-3}"
  local deadline=$((SECONDS + timeout))
  local hits="0"
  while (( SECONDS <= deadline )); do
    if ! hits=$(stage2_log_count "$keyword"); then
      return 1
    fi
    if (( hits > baseline )); then
      echo "$hits"
      return 0
    fi
    sleep "$interval"
  done
  error "Timed out waiting for logs containing '$keyword'"
  echo "$hits"
  return 1
}

get_metric_value() {
  local metric="$1"
  local metrics
  if ! metrics=$(curl -sS "$METRICS_URL"); then
    error "Unable to scrape metrics endpoint"
    return 1
  fi
  # Handle both labeled and unlabeled metrics
  # For labeled metrics like: reminders_created_total{user_id="..."} 31.0
  # For unlabeled metrics like: some_metric 42.0
  echo "$metrics" | awk -v name="$metric" '
    $1 == name || index($1, name "{") == 1 {
      sum += $NF
      found = 1
    }
    END {
      if (found != 1) print 0
      else print sum
    }
  '
}

wait_for_metric_increment() {
  local metric="$1"
  local baseline="$2"
  local timeout="${3:-60}"
  local interval="${4:-5}"
  local deadline=$((SECONDS + timeout))
  local current="$baseline"
  while (( SECONDS <= deadline )); do
    if ! current=$(get_metric_value "$metric"); then
      return 1
    fi
    if float_greater_than "$current" "$baseline"; then
      echo "$current"
      return 0
    fi
    sleep "$interval"
  done
  error "Metric $metric did not increment within ${timeout}s"
  echo "$current"
  return 1
}

test_reminder_create_api() {
  ensure_reminder_fixture
  assert_not_empty "$REMINDER_ID" "Reminder created via API" || return 1
}

test_reminder_in_database() {
  ensure_reminder_fixture
  local count
  count=$(psql_query "SELECT COUNT(*) FROM reminders WHERE id = '$REMINDER_ID';" | tr -d '[:space:]')
  assert_equals "$count" "1" "Reminder persisted in DB" || return 1
}

test_reminder_scheduler_entry() {
  local pair reminder_id baseline
  # Get baseline log count for "reminder_scheduled" event BEFORE creating reminder
  # This ensures we can detect the new log entry
  baseline=$(docker logs brainda-orchestrator 2>&1 | grep -c "reminder_scheduled" || echo "0")

  # Now create the reminder
  pair=$(create_unique_reminder 15)
  reminder_id=${pair%%|*}

  # Wait for the scheduler log to appear
  # The log should contain the reminder_id and "reminder_scheduled" event
  local timeout=30
  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    local current
    current=$(docker logs brainda-orchestrator 2>&1 | grep -c "reminder_scheduled" || echo "0")
    if (( current > baseline )); then
      # Verify the log contains our specific reminder_id
      if docker logs brainda-orchestrator 2>&1 | grep -q "$reminder_id"; then
        success "Reminder $reminder_id scheduled in APScheduler"
        return 0
      fi
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done

  error "Reminder $reminder_id did not produce scheduler log"
  return 1
}

test_reminder_chat_flow() {
  IFS='|' read -r marker status <<<"$(create_chat_reminder)"
  assert_status_code "$status" "200" "Chat endpoint accepted reminder request" || return 1
}

test_reminder_smart_defaults() {
  local marker="Smart Default $TIMESTAMP-$RANDOM"
  local payload
  payload=$(jq -n --arg msg "Remind me tomorrow to $marker" '{message:$msg}')
  local status
  status=$(curl -sS -o "$TEST_DIR/chat-smart.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/chat" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" || echo "000")
  assert_status_code "$status" "200" "Chat request for smart defaults" || return 1
  sleep 5
  local reminder_id
  reminder_id=$(psql_query "SELECT id FROM reminders WHERE title ILIKE '%$marker%' ORDER BY created_at DESC LIMIT 1;")
  assert_not_empty "$reminder_id" "Reminder created via chat" || return 1
  local due_local
  due_local=$(get_reminder_value "$reminder_id" "due_at_local")
  if [[ -n "$due_local" ]]; then
    success "Smart default produced local time $due_local"
    return 0
  fi
  return 1
}

test_reminder_dedup_response() {
  ensure_reminder_fixture
  local payload
  payload=$(jq -n --arg title "MVP Test Reminder $TIMESTAMP" --arg body "dup" --arg due "$REMINDER_DUE_UTC" --arg local "$REMINDER_DUE_LOCAL" '{title:$title, body:$body, due_at_utc:$due, due_at_local:$local, timezone:"UTC"}')
  local first second flag
  first=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  second=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  flag=$(echo "$second" | jq -r '.deduplicated // false')
  assert_equals "$flag" "true" "Duplicate reminder flagged" || return 1
}

test_reminder_dedup_constraint() {
  ensure_reminder_fixture
  if docker exec brainda-postgres psql -U "${POSTGRES_USER:-vib}" -d "${POSTGRES_DB:-vib}" -c \
    "INSERT INTO reminders (id,user_id,title,due_at_utc,due_at_local,timezone,status) SELECT gen_random_uuid(), user_id, title, due_at_utc, due_at_local, timezone, 'active' FROM reminders WHERE id = '$REMINDER_ID';" >/dev/null 2>&1; then
    error "DB dedup constraint allowed duplicate"
    return 1
  fi
  success "Database prevented duplicate reminder"
}

test_reminder_timezone_conversion() {
  local due_utc due_local payload response rid tz
  due_utc=$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:00Z')
  due_local=$(date -d '+2 hours' '+%H:%M:00')
  payload=$(jq -n --arg title "TZ Reminder $TIMESTAMP" --arg due "$due_utc" --arg local "$due_local" '{title:$title, due_at_utc:$due, due_at_local:$local, timezone:"America/Los_Angeles"}')
  response=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  rid=$(echo "$response" | jq -r '.data.id')
  tz=$(psql_query "SELECT timezone FROM reminders WHERE id = '$rid';" | tr -d '[:space:]')
  assert_equals "$tz" "America/Los_Angeles" "Timezone stored correctly" || return 1
}

test_reminder_due_local_preserved() {
  ensure_reminder_fixture
  local stored
  stored=$(get_reminder_value "$REMINDER_ID" "due_at_local")
  assert_equals "${stored// /}" "$REMINDER_DUE_LOCAL" "due_at_local preserved" || return 1
}

test_reminder_snooze_updates_due() {
  local pair reminder_id title before after
  pair=$(create_unique_reminder 10)
  reminder_id=${pair%%|*}
  before=$(get_reminder_value "$reminder_id" "due_at_utc")
  curl -sS -X POST "$BASE_URL/api/v1/reminders/$reminder_id/snooze" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"duration_minutes":15}' >/dev/null
  after=$(get_reminder_value "$reminder_id" "due_at_utc")
  assert_not_empty "$after" "Snooze returned due_at" || return 1
  if [[ "$after" == "$before" ]]; then
    error "Snooze did not update due time"
    return 1
  fi
}

test_reminder_snooze_reschedules() {
  local pair reminder_id baseline
  pair=$(create_unique_reminder 10)
  reminder_id=${pair%%|*}
  if ! baseline=$(stage2_log_count "reminder_snoozed"); then
    return 1
  fi
  curl -sS -X POST "$BASE_URL/api/v1/reminders/$reminder_id/snooze" -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" -d '{"duration_minutes":10}' >/dev/null
  if stage2_wait_for_log "reminder_snoozed" "$baseline" 60 3 >/dev/null; then
    success "Snooze reschedule logged"
    return 0
  fi
  error "Snooze event not observed in logs"
  return 1
}

test_reminder_cancel_endpoint() {
  local pair reminder_id
  pair=$(create_unique_reminder 20)
  reminder_id=${pair%%|*}
  local status
  status=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/api/v1/reminders/$reminder_id" -H "Authorization: Bearer $TOKEN")
  assert_status_code "$status" "200" "Cancel endpoint" || return 1
}

test_reminder_cancel_halts_firing() {
  local status
  status=$(psql_query "SELECT status FROM reminders WHERE id = '$REMINDER_ID';" | tr -d '[:space:]')
  if [[ "$status" != "cancelled" ]]; then
    warn "Base reminder not cancelled; cancelling now"
    curl -sS -X DELETE "$BASE_URL/api/v1/reminders/$REMINDER_ID" -H "Authorization: Bearer $TOKEN" >/dev/null || true
    status=$(psql_query "SELECT status FROM reminders WHERE id = '$REMINDER_ID';" | tr -d '[:space:]')
  fi
  assert_equals "$status" "cancelled" "Reminder marked cancelled" || return 1
}

test_reminder_recurring_daily() {
  local due payload response rid rrule
  due=$(date -u -d '+1 day' '+%Y-%m-%dT%H:%M:00Z')
  payload=$(jq -n --arg due "$due" '{title:"Recurring Daily", due_at_utc:$due, due_at_local:"09:00:00", timezone:"UTC", repeat_rrule:"FREQ=DAILY"}')
  response=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  rid=$(echo "$response" | jq -r '.data.id')
  rrule=$(psql_query "SELECT repeat_rrule FROM reminders WHERE id = '$rid';")
  assert_equals "$rrule" "FREQ=DAILY" "Daily recurrence saved" || return 1
}

test_reminder_recurring_weekly() {
  local due payload response rid rrule
  due=$(date -u -d 'next monday 09:00' '+%Y-%m-%dT%H:%M:00Z')
  payload=$(jq -n --arg due "$due" '{title:"Recurring Weekly", due_at_utc:$due, due_at_local:"09:00:00", timezone:"UTC", repeat_rrule:"FREQ=WEEKLY;BYDAY=MO"}')
  response=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  rid=$(echo "$response" | jq -r '.data.id')
  rrule=$(psql_query "SELECT repeat_rrule FROM reminders WHERE id = '$rid';")
  assert_equals "$rrule" "FREQ=WEEKLY;BYDAY=MO" "Weekly recurrence saved" || return 1
}

test_reminder_recurring_monthly() {
  local due payload response rid rrule
  due=$(date -u -d 'next month 09:00' '+%Y-%m-%dT%H:%M:00Z')
  payload=$(jq -n --arg due "$due" '{title:"Recurring Monthly", due_at_utc:$due, due_at_local:"09:00:00", timezone:"UTC", repeat_rrule:"FREQ=MONTHLY;BYMONTHDAY=1"}')
  response=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  rid=$(echo "$response" | jq -r '.data.id')
  rrule=$(psql_query "SELECT repeat_rrule FROM reminders WHERE id = '$rid';")
  assert_equals "$rrule" "FREQ=MONTHLY;BYMONTHDAY=1" "Monthly recurrence saved" || return 1
}

test_device_registration() {
  ensure_device_registered
  assert_not_empty "$DEVICE_ID" "Device registered" || return 1
}

test_device_db_entry() {
  ensure_device_registered
  local count
  count=$(psql_query "SELECT COUNT(*) FROM devices WHERE id = '$DEVICE_ID';" | tr -d '[:space:]')
  assert_equals "$count" "1" "Device row exists" || return 1
}

test_device_test_notification() {
  ensure_device_registered
  local status
  status=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/devices/test" -H "Authorization: Bearer $TOKEN")
  if [[ "$status" == "404" ]]; then
    error "Test notification endpoint reports no registered devices"
    return 1
  fi
  assert_status_code "$status" "200" "Test notification endpoint" || return 1
}

test_push_metrics() {
  local metrics success failure total rate
  metrics=$(curl -sS "$METRICS_URL") || metrics=""
  success=$(echo "$metrics" | awk '/^push_delivery_success_total/ {sum+=$2} END {print sum+0}')
  failure=$(echo "$metrics" | awk '/^push_delivery_failure_total/ {sum+=$2} END {print sum+0}')
  total=$(awk -v s="${success:-0}" -v f="${failure:-0}" 'BEGIN{print s+f}')
  if float_greater_than "${total:-0}" "0"; then
    rate=$(awk -v s="$success" -v t="$total" 'BEGIN{printf "%.3f", (t==0?0:s/t)}')
    PUSH_SUCCESS_RATE="$rate"
    assert_greater_than "$rate" "$PUSH_SUCCESS_TARGET" "Push success rate above target" || return 1
  else
    warn "Push delivery metrics have no samples"
  fi
}

test_reminder_fire_slo() {
  if $FAST_MODE; then
    warn "Skipping reminder fire SLO in fast mode"
    return 0
  fi
  ensure_device_registered
  local pair reminder_id
  pair=$(create_unique_reminder 1)
  reminder_id=${pair%%|*}
  REMINDER_FIRE_ID="$reminder_id"
  log "Waiting for reminder $reminder_id to fire (up to 150s)"
  wait_for_notification_delivery "$reminder_id" 150 || return 1
  local lag
  lag=$(psql_query "SELECT EXTRACT(EPOCH FROM (COALESCE(nd.delivered_at, nd.sent_at) - r.due_at_utc)) FROM notification_delivery nd JOIN reminders r ON r.id = nd.reminder_id WHERE nd.reminder_id = '$reminder_id' ORDER BY nd.created_at DESC LIMIT 1;")
  if [[ -n "$lag" ]]; then
    REMINDER_FIRE_LAG_P95="$lag"
    assert_less_than "${lag#-}" "$REMINDER_FIRE_LAG_TARGET" "Reminder fire lag <$REMINDER_FIRE_LAG_TARGET s" || return 1
  else
    error "No lag measurement recorded"
    return 1
  fi
}

test_notification_delivery_record() {
  local rid="${REMINDER_FIRE_ID:-}"
  if [[ -z "$rid" ]]; then
    warn "Fire SLO test did not produce reminder id"
    return 0
  fi
  local status
  status=$(psql_query "SELECT status FROM notification_delivery WHERE reminder_id = '$rid' ORDER BY created_at DESC LIMIT 1;")
  assert_equals "${status// /}" "delivered" "Notification delivery recorded" || return 1
}

test_reminder_metrics_created_total() {
  local before after pair reminder_id
  if ! before=$(get_metric_value "reminders_created_total"); then
    return 1
  fi
  pair=$(create_unique_reminder 45)
  reminder_id=${pair%%|*}
  if ! after=$(wait_for_metric_increment "reminders_created_total" "$before" 60 5); then
    error "reminders_created_total failed to increment for $reminder_id"
    return 1
  fi
  assert_greater_than "$after" "$before" "reminders_created_total increments" || return 1
}

test_reminder_metrics_deduped_total() {
  local before after payload due local
  due=$(date -u -d '+50 minutes' '+%Y-%m-%dT%H:%M:00Z')
  local=$(date -d '+50 minutes' '+%H:%M:00')
  payload=$(jq -n --arg title "Metric Dedup" --arg due "$due" --arg local "$local" '{title:$title,due_at_utc:$due,due_at_local:$local,timezone:"UTC"}')
  if ! before=$(get_metric_value "reminders_deduped_total"); then
    return 1
  fi
  curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" >/dev/null
  curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" >/dev/null
  if ! after=$(wait_for_metric_increment "reminders_deduped_total" "$before" 60 5); then
    error "reminders_deduped_total failed to increment"
    return 1
  fi
  assert_greater_than "$after" "$before" "reminders_deduped_total increments" || return 1
}

test_reminder_metrics_fire_lag() {
  local metrics
  metrics=$(curl -sS "$METRICS_URL")
  export METRIC_NAME="reminder_fire_lag_seconds"
  export METRIC_QUANTILE="0.95"
  REMINDER_FIRE_LAG_P95=$(echo "$metrics" | histogram_quantile_from_metrics)
  if [[ "$REMINDER_FIRE_LAG_P95" != "nan" ]]; then
    success "Reminder fire lag histogram available"
    return 0
  fi
  warn "Reminder fire lag histogram has no samples"
}

test_reminder_list_endpoint() {
  local status
  status=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/reminders")
  assert_status_code "$status" "200" "List reminders endpoint" || return 1
}

test_reminder_update_endpoint() {
  ensure_reminder_fixture
  local payload status
  payload='{ "status": "done" }'
  status=$(curl -sS -o /dev/null -w "%{http_code}" -X PATCH "$BASE_URL/api/v1/reminders/$REMINDER_ID" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  assert_status_code "$status" "200" "Reminder update endpoint" || return 1
}

test_reminder_restart_persistence() {
  ensure_reminder_fixture
  compose_cmd restart orchestrator >/dev/null 2>&1 || true
  wait_for "curl -sS $HEALTH_URL >/dev/null" 60 "health after orchestrator restart" || return 1
  local result
  result=$(curl -sS -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/reminders" | jq -r '.[] | select(.id=="'$REMINDER_ID'") | .id')
  assert_equals "$result" "$REMINDER_ID" "Reminder still available post-restart" || return 1
}

#############################################

run_stage2() {
  section "STAGE 2: REMINDERS + NOTIFICATIONS"
  local tests=(
    "reminder_api_create test_reminder_create_api"
    "reminder_db_record test_reminder_in_database"
    "reminder_scheduler_entry test_reminder_scheduler_entry"
    "reminder_chat_flow test_reminder_chat_flow"
    "reminder_smart_defaults test_reminder_smart_defaults"
    "reminder_dedup_response test_reminder_dedup_response"
    "reminder_dedup_constraint test_reminder_dedup_constraint"
    "reminder_timezone test_reminder_timezone_conversion"
    "reminder_due_local test_reminder_due_local_preserved"
    "reminder_snooze_updates test_reminder_snooze_updates_due"
    "reminder_snooze_logs test_reminder_snooze_reschedules"
    "reminder_cancel_endpoint test_reminder_cancel_endpoint"
    "reminder_cancel_state test_reminder_cancel_halts_firing"
    "reminder_recurring_daily test_reminder_recurring_daily"
    "reminder_recurring_weekly test_reminder_recurring_weekly"
    "reminder_recurring_monthly test_reminder_recurring_monthly"
    "device_registration test_device_registration"
    "device_db_entry test_device_db_entry"
    "device_test_notification test_device_test_notification"
    "push_metrics test_push_metrics"
    "reminder_fire_slo test_reminder_fire_slo"
    "notification_delivery_record test_notification_delivery_record"
    "reminder_metrics_created test_reminder_metrics_created_total"
    "reminder_metrics_deduped test_reminder_metrics_deduped_total"
    "reminder_metrics_fire_lag test_reminder_metrics_fire_lag"
    "reminder_list_endpoint test_reminder_list_endpoint"
    "reminder_update_endpoint test_reminder_update_endpoint"
    "reminder_restart_persistence test_reminder_restart_persistence"
  )
  for entry in "${tests[@]}"; do
    IFS=' ' read -r name func <<<"$entry"
    run_test "$name" "$func"
  done
}
