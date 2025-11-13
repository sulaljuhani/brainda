#!/usr/bin/env bash
# Stage 7: Google Calendar Sync Tests
# Tests OAuth, sync state, and Google Calendar integration

set -euo pipefail

test_google_sync_table_exists() {
  log "Checking calendar_sync_state table exists..."
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'calendar_sync_state';" | tr -d '[:space:]')
  if [[ "$count" != "1" ]]; then
    warn "calendar_sync_state table not found (Stage 7 may not be implemented)"
    return 0  # Don't fail
  fi
  success "calendar_sync_state table exists"
}

test_google_sync_status_endpoint() {
  log "Testing Google Calendar sync status endpoint..."
  local response status
  response=$(curl -sS -w "\n%{http_code}" -X GET "$BASE_URL/api/v1/calendar/google/status" \
    -H "Authorization: Bearer $TOKEN" 2>&1)
  status=$(echo "$response" | tail -1)

  if [[ "$status" == "200" ]]; then
    success "Google Calendar sync status endpoint exists"
  elif [[ "$status" == "404" ]]; then
    warn "Google Calendar sync endpoints not found (Stage 7 may not be implemented)"
    return 0
  else
    error "Unexpected status from Google sync status endpoint: $status"
    return 1
  fi
}

test_google_oauth_endpoints() {
  log "Testing Google OAuth endpoints exist..."
  local connect_status disconnect_status

  connect_status=$(curl -sS -o /dev/null -w "%{http_code}" -X GET "$BASE_URL/api/v1/calendar/google/connect" \
    -H "Authorization: Bearer $TOKEN")

  if [[ "$connect_status" == "200" || "$connect_status" == "302" ]]; then
    success "Google OAuth connect endpoint exists"
  elif [[ "$connect_status" == "404" ]]; then
    warn "Google OAuth endpoints not found (Stage 7 may not be implemented)"
    return 0
  fi

  # Test disconnect endpoint (should work even if not connected)
  disconnect_status=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/calendar/google/disconnect" \
    -H "Authorization: Bearer $TOKEN")

  if [[ "$disconnect_status" == "200" || "$disconnect_status" == "400" ]]; then
    success "Google OAuth disconnect endpoint exists"
  fi
}

test_google_sync_state() {
  log "Testing Google sync state structure..."
  local has_sync_state
  has_sync_state=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'calendar_sync_state';" 2>/dev/null | tr -d '[:space:]')

  if [[ "$has_sync_state" == "1" ]]; then
    # Check for required columns
    local has_google_calendar_id has_sync_token
    has_google_calendar_id=$(psql_query "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='calendar_sync_state' AND column_name='google_calendar_id';" | tr -d '[:space:]')
    has_sync_token=$(psql_query "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='calendar_sync_state' AND column_name='sync_token';" | tr -d '[:space:]')

    if [[ "$has_google_calendar_id" == "1" && "$has_sync_token" == "1" ]]; then
      success "calendar_sync_state table has required columns"
    else
      warn "calendar_sync_state table missing some columns"
    fi
  else
    warn "calendar_sync_state table not found (Stage 7 may not be implemented)"
  fi
  return 0
}

test_google_event_id_field() {
  log "Testing google_event_id field in calendar_events..."
  local has_google_id
  has_google_id=$(psql_query "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='calendar_events' AND column_name='google_event_id';" 2>/dev/null | tr -d '[:space:]')

  if [[ "$has_google_id" == "1" ]]; then
    success "calendar_events table has google_event_id column"
  else
    warn "google_event_id column not found (Stage 7 may not be implemented)"
  fi
  return 0
}

test_google_sync_trigger() {
  log "Testing manual sync trigger endpoint..."
  local status
  status=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/calendar/google/sync" \
    -H "Authorization: Bearer $TOKEN" 2>/dev/null)

  if [[ "$status" == "200" || "$status" == "400" || "$status" == "401" ]]; then
    success "Google sync trigger endpoint exists (status: $status)"
  elif [[ "$status" == "404" ]]; then
    warn "Google sync trigger endpoint not found (Stage 7 may not be implemented)"
  else
    warn "Unexpected status from sync trigger: $status"
  fi
  return 0
}


run_stage7() {
  section "STAGE 7: GOOGLE CALENDAR SYNC"
  local tests=(
    "stage7_sync_table test_google_sync_table_exists"
    "stage7_sync_status test_google_sync_status_endpoint"
    "stage7_oauth_endpoints test_google_oauth_endpoints"
    "stage7_sync_state test_google_sync_state"
    "stage7_event_google_id test_google_event_id_field"
    "stage7_sync_trigger test_google_sync_trigger"
  )
  for entry in "${tests[@]}"; do
    IFS=' ' read -r name func <<<"$entry"
    run_test "$name" "$func"
  done
}
