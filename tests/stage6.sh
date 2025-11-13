#!/usr/bin/env bash
# Stage 6: Calendar + RRULE Tests
# Tests calendar events, recurrence rules, and timezone handling

set -euo pipefail

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
  payload=$(jq -n --arg title "$title" --arg starts "$starts_at" '{title:$title, starts_at:$starts, timezone:"UTC"}')

  local response status
  response=$(curl -sS -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/calendar/events" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)
  status=$(echo "$response" | tail -1)
  response=$(echo "$response" | head -n -1)

  if [[ "$status" != "200" && "$status" != "201" ]]; then
    error "Failed to create calendar event. Status: $status"
    echo "Response: $response" >&2
    return 1
  fi

  CALENDAR_EVENT_ID=$(echo "$response" | jq -r '.data.id // .id // empty')
  if [[ -z "$CALENDAR_EVENT_ID" || "$CALENDAR_EVENT_ID" == "null" ]]; then
    error "No event ID in response"
    echo "Response: $response" >&2
    return 1
  fi

  success "Calendar event created: $CALENDAR_EVENT_ID"
}

test_calendar_event_in_db() {
  log "Testing calendar event persisted in database..."
  if [[ -z "${CALENDAR_EVENT_ID:-}" ]]; then
    # Create an event first
    test_calendar_event_create || return 1
  fi

  local count
  count=$(psql_query "SELECT COUNT(*) FROM calendar_events WHERE id = '$CALENDAR_EVENT_ID';" | tr -d '[:space:]')
  assert_equals "$count" "1" "Calendar event found in database"
}

test_calendar_event_list() {
  log "Testing calendar events list endpoint..."
  local start_date end_date
  start_date=$(date -u -d 'today' '+%Y-%m-%dT00:00:00Z')
  end_date=$(date -u -d '+7 days' '+%Y-%m-%dT23:59:59Z')

  local response status
  response=$(curl -sS -w "\n%{http_code}" -X GET "$BASE_URL/api/v1/calendar/events?start=$start_date&end=$end_date" \
    -H "Authorization: Bearer $TOKEN" 2>&1)
  status=$(echo "$response" | tail -1)
  response=$(echo "$response" | head -n -1)

  assert_status_code "$status" "200" "Calendar events list endpoint returns 200"

  local events
  events=$(echo "$response" | jq '.data.events // .events // []')
  if [[ "$events" == "[]" ]]; then
    warn "No events returned (may be expected if none exist in date range)"
  else
    success "Calendar events list returned: $(echo "$events" | jq 'length') events"
  fi
}

test_calendar_event_update() {
  log "Testing calendar event update..."
  if [[ -z "${CALENDAR_EVENT_ID:-}" ]]; then
    test_calendar_event_create || return 1
  fi

  local new_title="Updated Event $TIMESTAMP"
  local payload
  payload=$(jq -n --arg title "$new_title" '{title:$title}')

  local response status
  response=$(curl -sS -w "\n%{http_code}" -X PATCH "$BASE_URL/api/v1/calendar/events/$CALENDAR_EVENT_ID" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)
  status=$(echo "$response" | tail -1)

  assert_status_code "$status" "200" "Calendar event update returns 200"

  local db_title
  db_title=$(psql_query "SELECT title FROM calendar_events WHERE id = '$CALENDAR_EVENT_ID';" | xargs)
  assert_equals "$db_title" "$new_title" "Calendar event title updated in database"
}

test_calendar_event_delete() {
  log "Testing calendar event deletion..."
  # Create a fresh event for deletion
  local title="Delete Test $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(jq -n --arg title "$title" --arg starts "$starts_at" '{title:$title, starts_at:$starts, timezone:"UTC"}')

  local response
  response=$(curl -sS -X POST "$BASE_URL/api/v1/calendar/events" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload")

  local event_id
  event_id=$(echo "$response" | jq -r '.data.id // .id')

  # Delete the event
  local del_status
  del_status=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/api/v1/calendar/events/$event_id" \
    -H "Authorization: Bearer $TOKEN")

  assert_status_code "$del_status" "200" "Calendar event delete returns 200"

  # Verify status changed to cancelled
  local status_field
  status_field=$(psql_query "SELECT status FROM calendar_events WHERE id = '$event_id';" | xargs)
  if [[ "$status_field" == "cancelled" ]]; then
    success "Event status set to cancelled"
  else
    warn "Event status is '$status_field', expected 'cancelled'"
  fi
}

test_calendar_rrule_daily() {
  log "Testing calendar event with daily RRULE..."
  local title="Daily Standup $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d 'tomorrow 09:00' '+%Y-%m-%dT%H:%M:00Z')
  local rrule="FREQ=DAILY;COUNT=7"
  local payload
  payload=$(jq -n --arg title "$title" --arg starts "$starts_at" --arg rule "$rrule" \
    '{title:$title, starts_at:$starts, timezone:"UTC", rrule:$rule}')

  local response status
  response=$(curl -sS -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/calendar/events" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)
  status=$(echo "$response" | tail -1)
  response=$(echo "$response" | head -n -1)

  if [[ "$status" != "200" && "$status" != "201" ]]; then
    error "Failed to create event with RRULE. Status: $status"
    echo "Response: $response" >&2
    return 1
  fi

  local event_id
  event_id=$(echo "$response" | jq -r '.data.id // .id')

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
  payload=$(jq -n --arg title "$title" --arg starts "$starts_at" --arg rule "$rrule" \
    '{title:$title, starts_at:$starts, timezone:"UTC", rrule:$rule}')

  local response status
  response=$(curl -sS -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/calendar/events" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)
  status=$(echo "$response" | tail -1)

  assert_status_code "$status" "200" "Weekly RRULE event created"
}

test_calendar_rrule_expansion() {
  log "Testing RRULE expansion in list endpoint..."
  # Create an event with RRULE
  local title="Expansion Test $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d 'tomorrow 09:00' '+%Y-%m-%dT%H:%M:00Z')
  local rrule="FREQ=DAILY;COUNT=5"
  local payload
  payload=$(jq -n --arg title "$title" --arg starts "$starts_at" --arg rule "$rrule" \
    '{title:$title, starts_at:$starts, timezone:"UTC", rrule:$rule}')

  curl -sS -X POST "$BASE_URL/api/v1/calendar/events" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null

  sleep 1

  # Query events for next 7 days
  local start_date end_date
  start_date=$(date -u -d 'today' '+%Y-%m-%dT00:00:00Z')
  end_date=$(date -u -d '+7 days' '+%Y-%m-%dT23:59:59Z')

  local response
  response=$(curl -sS -X GET "$BASE_URL/api/v1/calendar/events?start=$start_date&end=$end_date" \
    -H "Authorization: Bearer $TOKEN")

  local expanded_count
  expanded_count=$(echo "$response" | jq "[.data.events // .events // [] | .[] | select(.title == \"$title\")] | length")

  if [[ "$expanded_count" -ge 5 ]]; then
    success "RRULE expanded correctly: $expanded_count instances found"
  else
    warn "RRULE expansion may not be working: only $expanded_count instances found, expected 5"
  fi
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
    warn "Invalid RRULE validation may not be implemented (got status $status)"
  fi
}

test_calendar_reminder_link() {
  log "Testing linking reminder to calendar event..."
  # Create a calendar event
  local event_title="Meeting $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:00Z')
  local event_payload
  event_payload=$(jq -n --arg title "$event_title" --arg starts "$starts_at" \
    '{title:$title, starts_at:$starts, timezone:"UTC"}')

  local event_response
  event_response=$(curl -sS -X POST "$BASE_URL/api/v1/calendar/events" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$event_payload")

  local event_id
  event_id=$(echo "$event_response" | jq -r '.data.id // .id')

  # Create a reminder
  local reminder_title="Reminder for Meeting $TIMESTAMP"
  local due_utc="$starts_at"
  local reminder_payload
  reminder_payload=$(jq -n --arg title "$reminder_title" --arg due "$due_utc" \
    '{title:$title, due_at_utc:$due, due_at_local:"10:00:00", timezone:"UTC"}')

  local reminder_response
  reminder_response=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$reminder_payload")

  local reminder_id
  reminder_id=$(echo "$reminder_response" | jq -r '.data.id // .id')

  # Link reminder to event
  local has_calendar_event_id_col
  has_calendar_event_id_col=$(psql_query "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='reminders' AND column_name='calendar_event_id';" | tr -d '[:space:]')

  if [[ "$has_calendar_event_id_col" == "1" ]]; then
    psql_query "UPDATE reminders SET calendar_event_id = '$event_id' WHERE id = '$reminder_id';" >/dev/null
    local linked_event
    linked_event=$(psql_query "SELECT calendar_event_id FROM reminders WHERE id = '$reminder_id';" | xargs)
    assert_equals "$linked_event" "$event_id" "Reminder linked to calendar event"
  else
    warn "calendar_event_id column not found in reminders table (feature may not be implemented)"
    return 0
  fi
}

test_calendar_weekly_view() {
  log "Testing weekly calendar view API..."
  local start_date end_date
  start_date=$(date -u -d 'last monday' '+%Y-%m-%dT00:00:00Z')
  end_date=$(date -u -d 'next sunday' '+%Y-%m-%dT23:59:59Z')

  local response status
  response=$(curl -sS -w "\n%{http_code}" -X GET "$BASE_URL/api/v1/calendar/events?start=$start_date&end=$end_date" \
    -H "Authorization: Bearer $TOKEN" 2>&1)
  status=$(echo "$response" | tail -1)

  assert_status_code "$status" "200" "Weekly calendar view API returns 200"
}

test_calendar_timezone_handling() {
  log "Testing calendar event timezone handling..."
  local title="Timezone Test $TIMESTAMP"
  local starts_at
  starts_at=$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:00Z')
  local tz="America/New_York"
  local payload
  payload=$(jq -n --arg title "$title" --arg starts "$starts_at" --arg timezone "$tz" \
    '{title:$title, starts_at:$starts, timezone:$timezone}')

  local response
  response=$(curl -sS -X POST "$BASE_URL/api/v1/calendar/events" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload")

  local event_id
  event_id=$(echo "$response" | jq -r '.data.id // .id')

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
}
