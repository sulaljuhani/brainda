#!/usr/bin/env bash
# Stage 5: Mobile + Idempotency Tests
# Tests idempotency keys, mobile endpoints, and concurrent request handling

set -euo pipefail

declare -a STAGE5_REMINDER_TITLES=()
declare -a STAGE5_IDEMPOTENCY_KEYS=()
declare -a STAGE5_TEMP_FILES=()

stage5_sql_literal() {
  local value="$1"
  value=${value//\'/\'\'}
  printf "'%s'" "$value"
}

stage5_register_temp_file() {
  local file="$1"
  STAGE5_TEMP_FILES+=("$file")
}

stage5_track_reminder() {
  local title="$1"
  if [[ -n "$title" ]]; then
    STAGE5_REMINDER_TITLES+=("$title")
  fi
}

stage5_track_idempotency_key() {
  local key="$1"
  if [[ -n "$key" ]]; then
    STAGE5_IDEMPOTENCY_KEYS+=("$key")
  fi
}

stage5_build_payload() {
  local title="$1"
  local due_utc="${2:-$(date -u -d '+30 minutes' '+%Y-%m-%dT%H:%M:00Z')}"
  jq -n --arg title "$title" --arg due "$due_utc" '{title:$title, due_at_utc:$due, due_at_local:"10:00:00", timezone:"UTC"}'
}

stage5_post_reminder() {
  local idem_key="$1"
  local payload="$2"
  local headers_file="${3:-}"
  local curl_args=(
    -sS
    -w "\n%{http_code}"
    -X POST "$BASE_URL/api/v1/reminders"
    -H "Authorization: Bearer $TOKEN"
    -H "Content-Type: application/json"
    -d "$payload"
  )
  if [[ -n "$idem_key" ]]; then
    curl_args+=(-H "Idempotency-Key: $idem_key")
  fi
  if [[ -n "$headers_file" ]]; then
    stage5_register_temp_file "$headers_file"
    curl_args=(
      -sS
      -D "$headers_file"
      -w "\n%{http_code}"
      -X POST "$BASE_URL/api/v1/reminders"
      -H "Authorization: Bearer $TOKEN"
      -H "Content-Type: application/json"
      -d "$payload"
    )
    if [[ -n "$idem_key" ]]; then
      curl_args+=(-H "Idempotency-Key: $idem_key")
    fi
  fi
  local response
  response=$(curl "${curl_args[@]}")
  STAGE5_LAST_STATUS=$(echo "$response" | tail -1 | tr -d '\r')
  STAGE5_LAST_BODY=$(echo "$response" | head -n -1)
}

stage5_assert_successful_post() {
  local action="$1"
  if [[ "$STAGE5_LAST_STATUS" != "200" && "$STAGE5_LAST_STATUS" != "201" ]]; then
    error "$action failed (status=$STAGE5_LAST_STATUS)"
    echo "Response: $STAGE5_LAST_BODY" >&2
    return 1
  fi
  return 0
}

stage5_extract_id() {
  local json="$1"
  jq -r '.data.id // .id // empty' <<<"$json"
}

stage5_wait_for_reminder_count() {
  local title="$1"
  local expected="$2"
  local timeout="${3:-10}"
  local attempt=0
  local safe_title
  safe_title=$(stage5_sql_literal "$title")
  while [[ $attempt -lt $timeout ]]; do
    local count
    count=$(psql_query "SELECT COUNT(*) FROM reminders WHERE title = $safe_title;" | tr -d '[:space:]')
    if [[ "$count" == "$expected" ]]; then
      return 0
    fi
    sleep 1
    attempt=$((attempt + 1))
  done
  error "Timed out waiting for reminder count $expected for title '$title'"
  return 1
}

stage5_cleanup_artifacts() {
  local title safe_title key safe_key file
  for title in "${STAGE5_REMINDER_TITLES[@]}"; do
    safe_title=$(stage5_sql_literal "$title")
    psql_query "DELETE FROM reminders WHERE title = $safe_title;" >/dev/null 2>&1 || true
  done
  for key in "${STAGE5_IDEMPOTENCY_KEYS[@]}"; do
    safe_key=$(stage5_sql_literal "$key")
    psql_query "DELETE FROM idempotency_keys WHERE idempotency_key = $safe_key;" >/dev/null 2>&1 || true
  done
  for file in "${STAGE5_TEMP_FILES[@]}"; do
    [[ -n "$file" ]] && rm -f "$file" 2>/dev/null || true
  done
}

if [[ -z "${STAGE5_CLEANUP_REGISTERED:-}" ]]; then
  STAGE5_CLEANUP_REGISTERED=1
  trap stage5_cleanup_artifacts EXIT
fi

test_idempotency_table_exists() {
  log "Checking idempotency_keys table exists..."
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'idempotency_keys';" | tr -d '[:space:]')
  if [[ "$count" != "1" ]]; then
    error "idempotency_keys table not found. Run migration 004_add_idempotency.sql"
    psql_query "\dt idempotency*" >&2
    return 1
  fi
  assert_equals "$count" "1" "idempotency_keys table exists"
}

test_idempotency_create_reminder() {
  log "Testing idempotency key with reminder creation..."
  local idem_key="test-idem-$TIMESTAMP-$RANDOM"
  local title="Idempotent Reminder $TIMESTAMP"
  local payload
  payload=$(stage5_build_payload "$title")

  log "Creating reminder with idempotency key: $idem_key"
  stage5_post_reminder "$idem_key" "$payload"
  stage5_assert_successful_post "Creating reminder" || return 1
  stage5_track_reminder "$title"
  stage5_track_idempotency_key "$idem_key"

  local reminder_id
  reminder_id=$(stage5_extract_id "$STAGE5_LAST_BODY")
  assert_not_empty "$reminder_id" "Reminder ID returned" || return 1

  local safe_key
  safe_key=$(stage5_sql_literal "$idem_key")
  local idem_count
  idem_count=$(psql_query "SELECT COUNT(*) FROM idempotency_keys WHERE idempotency_key = $safe_key;" | tr -d '[:space:]')
  assert_equals "$idem_count" "1" "Idempotency key stored in database"
}

test_idempotency_duplicate_prevention() {
  log "Testing duplicate prevention with same idempotency key..."
  local idem_key="test-dup-$TIMESTAMP-$RANDOM"
  local title="Duplicate Test $TIMESTAMP"
  local payload
  payload=$(stage5_build_payload "$title")

  log "First request with key: $idem_key"
  stage5_post_reminder "$idem_key" "$payload"
  stage5_assert_successful_post "First idempotent request" || return 1
  local id1
  id1=$(stage5_extract_id "$STAGE5_LAST_BODY")
  assert_not_empty "$id1" "First response includes reminder ID" || return 1
  stage5_track_reminder "$title"
  stage5_track_idempotency_key "$idem_key"

  log "Second request with same key: $idem_key"
  local headers_file="$TEST_DIR/headers-dup.txt"
  stage5_post_reminder "$idem_key" "$payload" "$headers_file"
  stage5_assert_successful_post "Second idempotent request" || return 1

  local id2
  id2=$(stage5_extract_id "$STAGE5_LAST_BODY")
  assert_not_empty "$id2" "Second response includes reminder ID" || return 1

  if [[ "$id1" != "$id2" ]]; then
    error "Different IDs returned for same idempotency key! id1=$id1 id2=$id2"
    echo "Response 2: $STAGE5_LAST_BODY" >&2
    return 1
  fi

  # Check for replay header
  local replay_header
  replay_header=$(grep -i "x-idempotency-replay" "$headers_file" || echo "")
  if [[ -z "$replay_header" ]]; then
    warn "X-Idempotency-Replay header not found (may not be implemented yet)"
  else
    success "X-Idempotency-Replay header present: $replay_header"
  fi

  # Verify only one reminder created in database
  local count
  local safe_title
  safe_title=$(stage5_sql_literal "$title")
  count=$(psql_query "SELECT COUNT(*) FROM reminders WHERE title = $safe_title;" | tr -d '[:space:]')
  assert_equals "$count" "1" "Only one reminder created despite duplicate request"
}

test_idempotency_header_replay() {
  log "Testing idempotency replay header..."
  local idem_key="test-replay-$TIMESTAMP-$RANDOM"
  local title="Replay Test $TIMESTAMP"
  local payload
  payload=$(stage5_build_payload "$title")

  # First request
  stage5_post_reminder "$idem_key" "$payload"
  stage5_assert_successful_post "Initial replay request" || return 1

  stage5_track_reminder "$title"
  stage5_track_idempotency_key "$idem_key"

  # Second request - should return cached response
  local headers_file="$TEST_DIR/replay-headers.txt"
  stage5_post_reminder "$idem_key" "$payload" "$headers_file"
  stage5_assert_successful_post "Replay response" || return 1

  if grep -qi "x-idempotency-replay" "$headers_file"; then
    success "X-Idempotency-Replay header found in response"
    return 0
  fi

  error "X-Idempotency-Replay header not found"
  return 1
}

test_idempotency_aggressive_retry() {
  log "Testing aggressive retry scenario (10 rapid requests with same key)..."
  local idem_key="test-aggressive-$TIMESTAMP-$RANDOM"
  local title="Aggressive Retry $TIMESTAMP"
  local payload
  payload=$(stage5_build_payload "$title")
  stage5_track_reminder "$title"
  stage5_track_idempotency_key "$idem_key"

  log "Sending 10 parallel requests with same idempotency key..."
  local files=()
  local pids=()
  for i in {1..10}; do
    local file="$TEST_DIR/aggressive-$i.json"
    stage5_register_temp_file "$file"
    (
      curl -sS --max-time 30 -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/reminders" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Idempotency-Key: $idem_key" \
        -H "Content-Type: application/json" \
        -d "$payload"
    ) >"$file" 2>&1 &
    pids+=($!)
    files+=("$file")
  done

  local wait_rc=0
  for pid in "${pids[@]}"; do
    if ! wait "$pid"; then
      wait_rc=1
    fi
  done

  if [[ $wait_rc -ne 0 ]]; then
    error "One or more concurrent reminder requests failed"
    return 1
  fi

  local canonical_id=""
  local file
  for file in "${files[@]}"; do
    local status
    status=$(tail -n1 "$file" | tr -d '\r')
    local body
    body=$(sed '$d' "$file")
    if [[ "$status" != "200" && "$status" != "201" ]]; then
      error "Concurrent request returned status $status"
      echo "Response: $body" >&2
      return 1
    fi
    local rid
    rid=$(echo "$body" | jq -r '.data.id // .id // empty')
    if [[ -z "$rid" || "$rid" == "null" ]]; then
      error "Concurrent request missing reminder ID"
      echo "Response: $body" >&2
      return 1
    fi
    if [[ -z "$canonical_id" ]]; then
      canonical_id="$rid"
    elif [[ "$canonical_id" != "$rid" ]]; then
      error "Multiple reminder IDs returned under concurrent load"
      return 1
    fi
  done

  log "Checking database for duplicate reminders..."
  if ! stage5_wait_for_reminder_count "$title" "1" 15; then
    psql_query "SELECT id, title, created_at FROM reminders WHERE title = $(stage5_sql_literal "$title");" >&2
    return 1
  fi
  success "Aggressive retry test passed: only 1 reminder created from 10 concurrent requests"
}

test_idempotency_different_keys() {
  log "Testing that different idempotency keys create separate reminders..."
  local title="Different Keys Test $TIMESTAMP"
  local payload
  payload=$(stage5_build_payload "$title")

  local key1="test-key1-$TIMESTAMP-$RANDOM"
  local key2="test-key2-$TIMESTAMP-$RANDOM"

  log "Creating reminder with key1: $key1"
  stage5_post_reminder "$key1" "$payload"
  stage5_assert_successful_post "Reminder with key1" || return 1
  stage5_track_reminder "$title"
  stage5_track_idempotency_key "$key1"

  log "Creating reminder with key2: $key2"
  local body_key1="$STAGE5_LAST_BODY"
  stage5_post_reminder "$key2" "$payload"
  stage5_assert_successful_post "Reminder with key2" || return 1
  stage5_track_idempotency_key "$key2"

  local id1 id2
  id1=$(stage5_extract_id "$body_key1")
  id2=$(stage5_extract_id "$STAGE5_LAST_BODY")

  if [[ "$id1" == "$id2" ]]; then
    error "Same reminder ID returned for different idempotency keys! id=$id1"
    return 1
  fi

  local safe_title
  safe_title=$(stage5_sql_literal "$title")
  local count
  count=$(psql_query "SELECT COUNT(*) FROM reminders WHERE title = $safe_title;" | tr -d '[:space:]')
  assert_equals "$count" "2" "Two separate reminders created with different idempotency keys"
}

test_idempotency_key_expiry() {
  log "Testing idempotency key expiry field..."
  local idem_key="test-expiry-$TIMESTAMP-$RANDOM"
  local title="Expiry Test $TIMESTAMP"
  local payload
  payload=$(stage5_build_payload "$title")

  stage5_post_reminder "$idem_key" "$payload"
  stage5_assert_successful_post "Creating reminder for expiry" || return 1
  stage5_track_reminder "$title"
  stage5_track_idempotency_key "$idem_key"

  local expires_at
  local safe_key
  safe_key=$(stage5_sql_literal "$idem_key")
  expires_at=$(psql_query "SELECT expires_at FROM idempotency_keys WHERE idempotency_key = $safe_key;" 2>/dev/null || echo "")

  if [[ -z "$expires_at" || "$expires_at" == "null" ]]; then
    error "expires_at field empty or not found"
    return 1
  fi

  success "Idempotency key has expiry: $expires_at"
}

test_idempotency_cleanup_job() {
  log "Testing idempotency cleanup job exists..."
  # Check if cleanup task is registered in Celery beat
  if docker exec vib-worker bash -c "celery -A app.worker inspect registered" 2>/dev/null | grep -q "cleanup.*idempotency"; then
    success "Idempotency cleanup task registered in Celery"
    return 0
  else
    warn "Idempotency cleanup task not found in Celery (may not be implemented yet)"
    return 0  # Don't fail, just warn
  fi
}

test_mobile_api_endpoints() {
  log "Testing mobile-specific API endpoints are accessible..."
  # Just verify the standard endpoints work (mobile uses same endpoints)
  local status
  status=$(curl -sS -o /dev/null -w "%{http_code}" -X GET "$BASE_URL/api/v1/reminders" \
    -H "Authorization: Bearer $TOKEN")
  assert_status_code "$status" "200" "Reminders endpoint accessible for mobile"
}

test_session_token_format() {
  log "Testing session token support (if implemented)..."
  # This checks if the backend supports session tokens as described in Stage 5
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'sessions';" 2>/dev/null | tr -d '[:space:]')
  if [[ "$count" == "1" ]]; then
    success "Sessions table exists (session token support implemented)"
  else
    warn "Sessions table not found (Stage 8 feature, may not be implemented in Stage 5)"
  fi
  return 0  # Don't fail
}

run_stage5() {
  section "STAGE 5: MOBILE + IDEMPOTENCY"
  local tests=(
    "stage5_idempotency_table test_idempotency_table_exists"
    "stage5_idempotency_create test_idempotency_create_reminder"
    "stage5_idempotency_duplicate test_idempotency_duplicate_prevention"
    "stage5_idempotency_header test_idempotency_header_replay"
    "stage5_idempotency_aggressive test_idempotency_aggressive_retry"
    "stage5_idempotency_different_key test_idempotency_different_keys"
    "stage5_idempotency_expiry test_idempotency_key_expiry"
    "stage5_idempotency_cleanup test_idempotency_cleanup_job"
    "stage5_mobile_endpoints test_mobile_api_endpoints"
    "stage5_session_token test_session_token_format"
  )
  for entry in "${tests[@]}"; do
    IFS=' ' read -r name func <<<"$entry"
    run_test "$name" "$func"
  done
}
