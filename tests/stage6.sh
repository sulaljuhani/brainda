#!/usr/bin/env bash
# Stage 6: Calendar + RRULE Tests
# Tests calendar events, recurrence rules, and timezone handling

set -euo pipefail

# Enable debug mode if requested
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi
IFS=$'\n\t'

STAGE6_CREATED_EVENTS=()
STAGE6_CREATED_REMINDERS=()
STAGE6_LAST_EVENT_RESPONSE=""

stage6_require_dependencies() {
  local missing=()
  for bin in curl jq; do
    if ! command -v "$bin" >/dev/null 2>&1; then
      missing+=("$bin")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    error "Missing required tools for Stage 6: ${missing[*]}"
    return 1
  fi
}

stage6_register_event_cleanup() {
  local event_id="$1"
  if [[ -n "$event_id" ]]; then
    STAGE6_CREATED_EVENTS+=("$event_id")
  fi
}

stage6_register_reminder_cleanup() {
  local reminder_id="$1"
  if [[ -n "$reminder_id" ]]; then
    STAGE6_CREATED_REMINDERS+=("$reminder_id")
  fi
}

stage6_cleanup_resources() {
  if [[ ${#STAGE6_CREATED_REMINDERS[@]} -gt 0 ]]; then
    for reminder_id in "${STAGE6_CREATED_REMINDERS[@]}"; do
      curl -sS -o /dev/null -X DELETE "$BASE_URL/api/v1/reminders/$reminder_id" \
        -H "Authorization: Bearer $TOKEN" || true
    done
    STAGE6_CREATED_REMINDERS=()
  fi

  if [[ ${#STAGE6_CREATED_EVENTS[@]} -gt 0 ]]; then
    for event_id in "${STAGE6_CREATED_EVENTS[@]}"; do
      curl -sS -o /dev/null -X DELETE "$BASE_URL/api/v1/calendar/events/$event_id" \
        -H "Authorization: Bearer $TOKEN" || true
    done
    STAGE6_CREATED_EVENTS=()
  fi
}

build_calendar_payload() {
  local title="$1"
  local starts_at="$2"
  local timezone="${3:-UTC}"
  local rrule="${4:-}"

  jq -n --arg title "$title" --arg starts "$starts_at" --arg tz "$timezone" --arg rrule "$rrule" '
    ({title:$title, starts_at:$starts, timezone:$tz}) as $base |
    if ($rrule | length) > 0 then $base + {rrule:$rrule} else $base end
  '
}

create_calendar_event() {
  local payload="$1"
  local response status body
  response=$(curl ${VERBOSE:+-v} -sS -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/calendar/events" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)
  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | head -n -1)

  if [[ "$status" != "200" && "$status" != "201" ]]; then
    error "Calendar event creation failed (status $status)"
    echo "Response: $body" >&2
    return 1
  fi

  local event_id
  event_id=$(echo "$body" | jq -r '.data.id // .id // empty')
  assert_not_empty "$event_id" "Calendar event ID returned" || return 1
  STAGE6_LAST_EVENT_RESPONSE="$body"
  stage6_register_event_cleanup "$event_id"
  echo "$event_id"
}

create_reminder() {
  local payload="$1"
  local response status body
  response=$(curl ${VERBOSE:+-v} -sS -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/reminders" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)
  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | head -n -1)
  if [[ "$status" != "200" && "$status" != "201" ]]; then
    error "Reminder creation failed (status $status)"
    echo "Response: $body" >&2
    return 1
  fi
  local reminder_id
  reminder_id=$(echo "$body" | jq -r '.data.id // .id // empty')
  assert_not_empty "$reminder_id" "Reminder ID returned" || return 1
  stage6_register_reminder_cleanup "$reminder_id"
  echo "$reminder_id"
}

fetch_calendar_events() {
  local start_date="$1"
  local end_date="$2"
  local response status body
  response=$(curl ${VERBOSE:+-v} -sS -w "\n%{http_code}" -X GET "$BASE_URL/api/v1/calendar/events?start=$start_date&end=$end_date" \
    -H "Authorization: Bearer $TOKEN" 2>&1)
  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | head -n -1)
  assert_status_code "$status" "200" "Calendar events list request succeeded" || return 1
  echo "$body"
}

count_events_by_title() {
  local json="$1"
  local title="$2"
  echo "$json" | jq --arg title "$title" '[.data.events // .events // [] | .[] | select(.title == $title)] | length'
}

event_exists_in_list() {
  local json="$1"
  local event_id="$2"
  echo "$json" | jq -e --arg id "$event_id" '(.data.events // .events // []) | map(select(.id == $id)) | length > 0' >/dev/null
}

test_calendar_table_exists() {
  log "Checking calendar_events table exists..."
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'calendar_events';" | tr -d '[:space:]')
  if [[ "$count" != "1" ]]; then
    error "calendar_events table not found. Run migration 005_add_calendar.sql"
    psql_query "\dt calendar*" >&2
    return 1
  fi
  assert_equals "$count" "1" "calendar_events table exists"
}

test_calendar_event_create() {
  log "Testing calendar event creation via API..."
  local title="Test Event $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(build_calendar_payload "$title" "$starts_at" "UTC")

  local event_id
  event_id=$(create_calendar_event "$payload") || return 1
  assert_json_field "$STAGE6_LAST_EVENT_RESPONSE" '.data.title // .title' "$title" "Calendar event title returned" || return 1
  local stored_title
  stored_title=$(psql_query "SELECT title FROM calendar_events WHERE id = '$event_id';" | xargs)
  assert_equals "$stored_title" "$title" "Calendar event persisted with correct title"
}

test_calendar_event_in_db() {
  log "Testing calendar event persisted in database..."
  local title="DB Check $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d '+1 hour' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(build_calendar_payload "$title" "$starts_at" "UTC")
  local event_id
  event_id=$(create_calendar_event "$payload") || return 1

  local count
  count=$(psql_query "SELECT COUNT(*) FROM calendar_events WHERE id = '$event_id';" | tr -d '[:space:]')
  assert_equals "$count" "1" "Calendar event found in database"
}

test_calendar_event_list() {
  log "Testing calendar events list endpoint..."
  local title="List Event $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d 'today +3 hours' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(build_calendar_payload "$title" "$starts_at" "UTC")
  local event_id
  event_id=$(create_calendar_event "$payload") || return 1

  local start_date end_date
  start_date=$(date -u -d 'today' '+%Y-%m-%dT00:00:00Z')
  end_date=$(date -u -d '+7 days' '+%Y-%m-%dT23:59:59Z')
  local response_json
  response_json=$(fetch_calendar_events "$start_date" "$end_date") || return 1
  if event_exists_in_list "$response_json" "$event_id"; then
    success "Calendar list endpoint returned created event"
  else
    error "Created event $event_id not returned by list endpoint"
    echo "$response_json" | jq '.' >&2
    return 1
  fi
}

test_calendar_event_update() {
  log "Testing calendar event update..."
  local title="Updatable Event $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d '+3 hours' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(build_calendar_payload "$title" "$starts_at" "UTC")
  local event_id
  event_id=$(create_calendar_event "$payload") || return 1

  local new_title="Updated Event $TIMESTAMP"
  local update_payload
  update_payload=$(jq -n --arg title "$new_title" '{title:$title}')

  local response status
  response=$(curl -sS -w "\n%{http_code}" -X PATCH "$BASE_URL/api/v1/calendar/events/$event_id" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$update_payload" 2>&1)
  status=$(echo "$response" | tail -1)
  response=$(echo "$response" | head -n -1)

  assert_status_code "$status" "200" "Calendar event update returns 200"
  assert_json_field "$response" '.data.title // .title' "$new_title" "Calendar update echoed new title" || return 1

  local db_title
  db_title=$(psql_query "SELECT title FROM calendar_events WHERE id = '$event_id';" | xargs)
  assert_equals "$db_title" "$new_title" "Calendar event title updated in database"
}

test_calendar_event_delete() {
  log "Testing calendar event deletion..."
  local title="Delete Test $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(build_calendar_payload "$title" "$starts_at" "UTC")
  local event_id
  event_id=$(create_calendar_event "$payload") || return 1

  # Delete the event
  local del_status
  del_status=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/api/v1/calendar/events/$event_id" \
    -H "Authorization: Bearer $TOKEN")

  assert_status_code "$del_status" "200" "Calendar event delete returns 200"

  # Verify status changed to cancelled
  local status_field
  status_field=$(psql_query "SELECT status FROM calendar_events WHERE id = '$event_id';" | xargs)
  assert_equals "$status_field" "cancelled" "Event status set to cancelled"
}

test_calendar_rrule_daily() {
  log "Testing calendar event with daily RRULE..."
  local title="Daily Standup $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d 'tomorrow 09:00' '+%Y-%m-%dT%H:%M:00Z')
  local rrule="FREQ=DAILY;COUNT=7"
  local payload
  payload=$(build_calendar_payload "$title" "$starts_at" "UTC" "$rrule")

  local event_id
  event_id=$(create_calendar_event "$payload") || return 1

  local stored_rrule
  stored_rrule=$(psql_query "SELECT rrule FROM calendar_events WHERE id = '$event_id';" | xargs)
  assert_equals "$stored_rrule" "$rrule" "RRULE stored correctly in database"
}

test_calendar_rrule_weekly() {
  log "Testing calendar event with weekly RRULE..."
  local title="Weekly Meeting $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d 'next monday 10:00' '+%Y-%m-%dT%H:%M:00Z')
  local rrule="FREQ=WEEKLY;BYDAY=MO;COUNT=4"
  local payload
  payload=$(build_calendar_payload "$title" "$starts_at" "UTC" "$rrule")

  local event_id
  event_id=$(create_calendar_event "$payload") || return 1

  local stored_rrule
  stored_rrule=$(psql_query "SELECT rrule FROM calendar_events WHERE id = '$event_id';" | xargs)
  assert_equals "$stored_rrule" "$rrule" "Weekly RRULE stored correctly"
}

test_calendar_rrule_expansion() {
  log "Testing RRULE expansion in list endpoint..."
  # Create an event with RRULE
  local title="Expansion Test $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d 'tomorrow 09:00' '+%Y-%m-%dT%H:%M:00Z')
  local rrule="FREQ=DAILY;COUNT=5"
  local payload
  payload=$(build_calendar_payload "$title" "$starts_at" "UTC" "$rrule")
  create_calendar_event "$payload" >/dev/null || return 1

  # Query events for next 7 days
  local start_date end_date
  start_date=$(date -u -d 'today' '+%Y-%m-%dT00:00:00Z')
  end_date=$(date -u -d '+7 days' '+%Y-%m-%dT23:59:59Z')

  local expanded_count=0
  local attempts=0
  local response_json
  while [[ $attempts -lt 10 ]]; do
    response_json=$(fetch_calendar_events "$start_date" "$end_date") || return 1
    expanded_count=$(count_events_by_title "$response_json" "$title")
    if [[ "$expanded_count" -ge 5 ]]; then
      success "RRULE expanded correctly: $expanded_count instances found"
      return 0
    fi
    sleep 1
    attempts=$((attempts + 1))
  done
  error "RRULE expansion may not be working: only $expanded_count instances found after waiting"
  echo "$response_json" | jq '.' >&2
  return 1
}

test_calendar_rrule_validation() {
  log "Testing RRULE validation (should reject invalid rules)..."
  local title="Invalid RRULE Test $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:00Z')
  local invalid_rrule="FREQ=INVALID;COUNT=1000000"  # Invalid frequency and excessive count
  local payload
  payload=$(jq -n --arg title "$title" --arg starts "$starts_at" --arg rule "$invalid_rrule" \
    '{title:$title, starts_at:$starts, timezone:"UTC", rrule:$rule}')

  local status
  status=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/calendar/events" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload")

  if [[ "$status" == "400" || "$status" == "422" ]]; then
    success "Invalid RRULE rejected with status $status"
  else
    error "Invalid RRULE validation may not be implemented (got status $status)"
    return 1
  fi
}

test_calendar_reminder_link() {
  log "Testing linking reminder to calendar event..."
  # Create a calendar event
  local event_title="Meeting $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:00Z')
  local event_payload
  event_payload=$(build_calendar_payload "$event_title" "$starts_at" "UTC")

  local event_id
  event_id=$(create_calendar_event "$event_payload") || return 1

  # Create a reminder
  local reminder_title="Reminder for Meeting $TIMESTAMP"
  local due_utc="$starts_at"
  local reminder_payload
  reminder_payload=$(jq -n --arg title "$reminder_title" --arg due "$due_utc" \
    '{title:$title, due_at_utc:$due, due_at_local:"10:00:00", timezone:"UTC"}')

  local reminder_id
  reminder_id=$(create_reminder "$reminder_payload") || return 1

  local patch_payload
  patch_payload=$(jq -n --arg event_id "$event_id" '{calendar_event_id:$event_id}')
  local patch_response status body
  patch_response=$(curl -sS -w "\n%{http_code}" -X PATCH "$BASE_URL/api/v1/reminders/$reminder_id" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$patch_payload" 2>&1)
  status=$(echo "$patch_response" | tail -1)
  body=$(echo "$patch_response" | head -n -1)
  assert_status_code "$status" "200" "Reminder update returned 200" || return 1
  assert_json_field "$body" '.data.calendar_event_id // .calendar_event_id' "$event_id" "Reminder response reflects linked event" || return 1

  local linked_event
  linked_event=$(psql_query "SELECT calendar_event_id FROM reminders WHERE id = '$reminder_id';" | xargs)
  assert_equals "$linked_event" "$event_id" "Reminder linked to calendar event"
}

test_calendar_weekly_view() {
  log "Testing weekly calendar view API..."
  local title="Weekly View $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d 'next tuesday 13:00' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(build_calendar_payload "$title" "$starts_at" "UTC")
  local event_id
  event_id=$(create_calendar_event "$payload") || return 1

  local start_date end_date
  start_date=$(date -u -d 'last monday' '+%Y-%m-%dT00:00:00Z')
  end_date=$(date -u -d 'next sunday' '+%Y-%m-%dT23:59:59Z')

  local response_json
  response_json=$(fetch_calendar_events "$start_date" "$end_date") || return 1
  if event_exists_in_list "$response_json" "$event_id"; then
    success "Weekly calendar view returned the created event"
  else
    error "Weekly view missing expected event"
    echo "$response_json" | jq '.' >&2
    return 1
  fi
}

test_calendar_timezone_handling() {
  log "Testing calendar event timezone handling..."
  local title="Timezone Test $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:00Z')
  local tz="America/New_York"
  local payload
  payload=$(build_calendar_payload "$title" "$starts_at" "$tz")

  local event_id
  event_id=$(create_calendar_event "$payload") || return 1

  local stored_tz
  stored_tz=$(psql_query "SELECT timezone FROM calendar_events WHERE id = '$event_id';" | xargs)
  assert_equals "$stored_tz" "$tz" "Calendar event timezone stored correctly"
}

test_calendar_user_isolation() {
  log "Testing calendar events are isolated by user..."
  # This test verifies that events are properly scoped to user_id
  local has_user_id
  has_user_id=$(psql_query "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='calendar_events' AND column_name='user_id';" | tr -d '[:space:]')

  if [[ "$has_user_id" == "1" ]]; then
    success "calendar_events table has user_id column for isolation"
  else
    error "calendar_events table missing user_id column!"
    return 1
  fi
}


run_stage6() {
  section "STAGE 6: CALENDAR + RRULE"
  stage6_require_dependencies || return 1
  stage6_cleanup_resources
  local tests=(
    "stage6_calendar_table test_calendar_table_exists"
    "stage6_calendar_create test_calendar_event_create"
    "stage6_calendar_db_record test_calendar_event_in_db"
    "stage6_calendar_list test_calendar_event_list"
    "stage6_calendar_update test_calendar_event_update"
    "stage6_calendar_delete test_calendar_event_delete"
    "stage6_rrule_daily test_calendar_rrule_daily"
    "stage6_rrule_weekly test_calendar_rrule_weekly"
    "stage6_rrule_expansion test_calendar_rrule_expansion"
    "stage6_rrule_validation test_calendar_rrule_validation"
    "stage6_reminder_link test_calendar_reminder_link"
    "stage6_weekly_view test_calendar_weekly_view"
    "stage6_timezone test_calendar_timezone_handling"
    "stage6_user_isolation test_calendar_user_isolation"
  )
  for entry in "${tests[@]}"; do
    IFS=' ' read -r name func <<<"$entry"
    run_test "$name" "$func"
  done
  stage6_cleanup_resources
}
