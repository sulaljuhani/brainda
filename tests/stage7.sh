#!/usr/bin/env bash
# Stage 7: Google Calendar Sync Tests
# -----------------------------------
# Validates the Google Calendar OAuth endpoints, sync-state schema, and
# manual sync triggers. Requires `tests/common.sh` to be sourced along with
# the following environment variables:
#   * BASE_URL – root URL of the vib-api service (e.g., http://localhost:8000)
#   * TOKEN – API token with permission to call calendar endpoints
#   * POSTGRES_USER / POSTGRES_DB – optional overrides for psql_query
#
# Set STAGE7_OPTIONAL=true to downgrade missing features to warnings instead of
# hard failures.

set -euo pipefail

STAGE7_OPTIONAL="${STAGE7_OPTIONAL:-false}"

stage7_fail_or_skip() {
  local message="$1"
  if [[ "$STAGE7_OPTIONAL" == "true" ]]; then
    warn "$message (Stage 7 marked optional, skipping strict failure)"
    return 0
  fi
  error "$message"
  return 1
}

require_env_var() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    error "Missing required environment variable: $var_name"
    exit 1
  fi
}

require_function() {
  local func_name="$1"
  if ! declare -F "$func_name" >/dev/null; then
    error "Required function '$func_name' is not available. Did you source tests/common.sh?"
    exit 1
  fi
}

ensure_stage7_prereqs() {
  require_env_var "BASE_URL"
  require_env_var "TOKEN"
  require_function "psql_query"
  command -v curl >/dev/null 2>&1 || {
    error "curl is required for Stage 7 tests"
    exit 1
  }
  command -v python3 >/dev/null 2>&1 || {
    error "python3 is required for JSON validation in Stage 7 tests"
    exit 1
  }
}

assert_table_exists() {
  local table="$1"
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '$table';" | tr -d '[:space:]')
  if [[ "$count" != "1" ]]; then
    stage7_fail_or_skip "Required table '$table' not found"
    return $?
  fi
  success "Table '$table' exists"
}

assert_columns_exist() {
  local table="$1"
  shift
  local missing_columns=()
  local column
  for column in "$@"; do
    local col_count
    col_count=$(psql_query "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='$table' AND column_name='$column';" | tr -d '[:space:]')
    if [[ "$col_count" != "1" ]]; then
      missing_columns+=("$column")
    fi
  done
  if [[ ${#missing_columns[@]} -gt 0 ]]; then
    stage7_fail_or_skip "Table '$table' missing columns: ${missing_columns[*]}"
    return $?
  fi
  success "Table '$table' has columns: $*"
}

log_http_failure() {
  local status="$1"
  local body="$2"
  warn "HTTP $status response body: $body"
}

capture_http_response() {
  local method="$1"
  local url="$2"
  shift 2
  local extra=("$@")
  curl -sS -w "\n%{http_code}" -X "$method" "$url" "${extra[@]}"
}

test_google_sync_table_exists() {
  log "Checking calendar_sync_state table and required columns exist..."
  assert_table_exists "calendar_sync_state" || return $?
  assert_columns_exist "calendar_sync_state" \
    "user_id" \
    "google_calendar_id" \
    "sync_token" \
    "last_sync_at" \
    "sync_enabled" \
    "sync_direction" \
    "created_at" \
    "updated_at"
}

test_google_sync_status_endpoint() {
  log "Testing Google Calendar sync status endpoint..."
  local response status body validation_error
  response=$(capture_http_response "GET" "$BASE_URL/api/v1/calendar/google/status" -H "Authorization: Bearer $TOKEN")
  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  if [[ "$status" != "200" ]]; then
    log_http_failure "$status" "$body"
    stage7_fail_or_skip "Expected HTTP 200 from google status endpoint, got $status"
    return $?
  fi

  if ! validation_error=$(python3 - <<'PY' "$body" 2>&1); then
import json, sys
body = sys.argv[1]
try:
    data = json.loads(body)
except json.JSONDecodeError as exc:
    sys.stderr.write(f"invalid JSON: {exc}")
    sys.exit(1)
required = ["connected", "sync_direction", "last_sync", "google_calendar_id"]
missing = [field for field in required if field not in data]
if missing:
    sys.stderr.write("missing fields: " + ", ".join(missing))
    sys.exit(1)
if not isinstance(data["connected"], bool):
    sys.stderr.write("'connected' must be boolean")
    sys.exit(1)
PY
  then
    error "Invalid google sync status response: $validation_error"
    return 1
  fi

  success "Google Calendar sync status endpoint returned expected JSON"
}

test_google_oauth_endpoints() {
  log "Testing Google OAuth endpoints exist..."
  local response status body validation_error

  response=$(capture_http_response "GET" "$BASE_URL/api/v1/calendar/google/connect" -H "Authorization: Bearer $TOKEN")
  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  if [[ "$status" != "200" ]]; then
    log_http_failure "$status" "$body"
    stage7_fail_or_skip "Expected HTTP 200 from google connect endpoint, got $status"
    return $?
  fi

  if ! validation_error=$(python3 - <<'PY' "$body" 2>&1); then
import json, sys
data = json.loads(sys.argv[1])
url = data.get("authorization_url")
state = data.get("state")
if not url or "accounts.google.com" not in url:
    sys.stderr.write("authorization_url missing or malformed")
    sys.exit(1)
if not state or len(state) < 10:
    sys.stderr.write("state token missing or too short")
    sys.exit(1)
PY
  then
    error "Invalid google connect response: $validation_error"
    return 1
  fi

  success "Google OAuth connect endpoint returned authorization URL"

  response=$(capture_http_response "POST" "$BASE_URL/api/v1/calendar/google/disconnect" -H "Authorization: Bearer $TOKEN")
  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  if [[ "$status" != "200" ]]; then
    log_http_failure "$status" "$body"
    stage7_fail_or_skip "Expected HTTP 200 from google disconnect endpoint, got $status"
    return $?
  fi

  if ! validation_error=$(python3 - <<'PY' "$body" 2>&1); then
import json, sys
data = json.loads(sys.argv[1])
if not data.get("success"):
    sys.stderr.write("success flag missing or false")
    sys.exit(1)
if not data.get("message"):
    sys.stderr.write("disconnect message missing")
    sys.exit(1)
PY
  then
    error "Invalid google disconnect response: $validation_error"
    return 1
  fi

  success "Google OAuth disconnect endpoint returned success payload"
}

test_google_sync_state() {
  log "Testing Google sync state structure..."
  assert_table_exists "calendar_sync_state" || return $?
  assert_columns_exist "calendar_sync_state" \
    "user_id" \
    "google_calendar_id" \
    "sync_token" \
    "last_sync_at" \
    "sync_enabled" \
    "sync_direction"
}

test_google_event_id_field() {
  log "Testing google_event_id field in calendar_events..."
  assert_table_exists "calendar_events" || return $?
  assert_columns_exist "calendar_events" "google_event_id" "google_calendar_id" "source"
}

test_google_sync_trigger() {
  log "Testing manual sync trigger endpoint..."
  local response status body detail
  response=$(capture_http_response "POST" "$BASE_URL/api/v1/calendar/google/sync" -H "Authorization: Bearer $TOKEN")
  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  case "$status" in
    200)
      if ! python3 - <<'PY' "$body" >/dev/null 2>&1; then
import json, sys
data = json.loads(sys.argv[1])
if not data.get("success"):
    raise SystemExit("success flag missing or false")
PY
      then
        error "Manual sync trigger response missing success flag"
        return 1
      fi
      success "Manual sync trigger accepted request"
      ;;
    400)
      detail=$(python3 - <<'PY' "$body" 2>/dev/null || true)
import json, sys
try:
    data = json.loads(sys.argv[1])
except json.JSONDecodeError:
    sys.exit(0)
print(data.get("detail", ""))
PY
      if [[ -n "$detail" ]]; then
        warn "Manual sync trigger returned 400: $detail"
      else
        warn "Manual sync trigger returned 400 without detail"
      fi
      stage7_fail_or_skip "Manual sync trigger is unavailable while Google Calendar is disconnected"
      return $?
      ;;
    401)
      log_http_failure "$status" "$body"
      return 1
      ;;
    *)
      log_http_failure "$status" "$body"
      stage7_fail_or_skip "Unexpected status from manual sync trigger: $status"
      return $?
      ;;
  esac
}

test_google_sync_settings_endpoint() {
  log "Testing Google sync settings PATCH endpoint..."
  local response status body validation_error
  response=$(capture_http_response "PATCH" "$BASE_URL/api/v1/calendar/google/settings" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{}')
  status=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  if [[ "$status" != "200" ]]; then
    log_http_failure "$status" "$body"
    stage7_fail_or_skip "Expected HTTP 200 from google settings endpoint, got $status"
    return $?
  fi

  if ! validation_error=$(python3 - <<'PY' "$body" 2>&1); then
import json, sys
data = json.loads(sys.argv[1])
if not data.get("success"):
    sys.stderr.write("success flag missing or false")
    sys.exit(1)
if "state" not in data:
    sys.stderr.write("state payload missing")
    sys.exit(1)
PY
  then
    error "Invalid google settings response: $validation_error"
    return 1
  fi

  success "Google sync settings endpoint returned success payload"
}

run_stage7() {
  section "STAGE 7: GOOGLE CALENDAR SYNC"
  ensure_stage7_prereqs
  local tests=(
    "stage7_sync_table test_google_sync_table_exists"
    "stage7_sync_status test_google_sync_status_endpoint"
    "stage7_oauth_endpoints test_google_oauth_endpoints"
    "stage7_sync_state test_google_sync_state"
    "stage7_event_google_id test_google_event_id_field"
    "stage7_sync_settings test_google_sync_settings_endpoint"
    "stage7_sync_trigger test_google_sync_trigger"
  )
  for entry in "${tests[@]}"; do
    IFS=' ' read -r name func <<<"$entry"
    run_test "$name" "$func"
  done
}
