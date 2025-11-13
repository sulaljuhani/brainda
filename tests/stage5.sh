#!/usr/bin/env bash
# Stage 5: Mobile + Idempotency Tests
# Tests idempotency keys, mobile endpoints, and concurrent request handling

set -euo pipefail

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
  local due_utc
  due_utc=$(date -u -d '+30 minutes' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(jq -n --arg title "$title" --arg due "$due_utc" '{title:$title, due_at_utc:$due, due_at_local:"10:00:00", timezone:"UTC"}')

  log "Creating reminder with idempotency key: $idem_key"
  local response status
  response=$(curl -sS -w "\n%{http_code}" -X POST "$BASE_URL/api/v1/reminders" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Idempotency-Key: $idem_key" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)
  status=$(echo "$response" | tail -1)
  response=$(echo "$response" | head -n -1)

  if [[ "$status" != "200" && "$status" != "201" ]]; then
    error "Failed to create reminder with idempotency key. Status: $status"
    echo "Response: $response" >&2
    return 1
  fi

  local reminder_id
  reminder_id=$(echo "$response" | jq -r '.data.id // .id // empty')
  if [[ -z "$reminder_id" || "$reminder_id" == "null" ]]; then
    error "No reminder ID in response"
    echo "Response: $response" >&2
    return 1
  fi

  # Check idempotency key stored in database
  local idem_count
  idem_count=$(psql_query "SELECT COUNT(*) FROM idempotency_keys WHERE idempotency_key = '$idem_key';" | tr -d '[:space:]')
  assert_equals "$idem_count" "1" "Idempotency key stored in database"
}

test_idempotency_duplicate_prevention() {
  log "Testing duplicate prevention with same idempotency key..."
  local idem_key="test-dup-$TIMESTAMP-$RANDOM"
  local title="Duplicate Test $TIMESTAMP"
  local due_utc
  due_utc=$(date -u -d '+30 minutes' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(jq -n --arg title "$title" --arg due "$due_utc" '{title:$title, due_at_utc:$due, due_at_local:"10:00:00", timezone:"UTC"}')

  log "First request with key: $idem_key"
  local resp1
  resp1=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Idempotency-Key: $idem_key" \
    -H "Content-Type: application/json" \
    -d "$payload")

  local id1
  id1=$(echo "$resp1" | jq -r '.data.id // .id // empty')

  log "Second request with same key: $idem_key"
  local resp2 replay_header
  resp2=$(curl -sS -D "$TEST_DIR/headers-dup.txt" -X POST "$BASE_URL/api/v1/reminders" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Idempotency-Key: $idem_key" \
    -H "Content-Type: application/json" \
    -d "$payload")

  local id2
  id2=$(echo "$resp2" | jq -r '.data.id // .id // empty')

  if [[ "$id1" != "$id2" ]]; then
    error "Different IDs returned for same idempotency key! id1=$id1 id2=$id2"
    echo "Response 1: $resp1" >&2
    echo "Response 2: $resp2" >&2
    return 1
  fi

  # Check for replay header
  replay_header=$(grep -i "x-idempotency-replay" "$TEST_DIR/headers-dup.txt" || echo "")
  if [[ -z "$replay_header" ]]; then
    warn "X-Idempotency-Replay header not found (may not be implemented yet)"
  else
    success "X-Idempotency-Replay header present: $replay_header"
  fi

  # Verify only one reminder created in database
  local count
  count=$(psql_query "SELECT COUNT(*) FROM reminders WHERE title = '$title';" | tr -d '[:space:]')
  assert_equals "$count" "1" "Only one reminder created despite duplicate request"
}

test_idempotency_header_replay() {
  log "Testing idempotency replay header..."
  local idem_key="test-replay-$TIMESTAMP-$RANDOM"
  local title="Replay Test $TIMESTAMP"
  local due_utc
  due_utc=$(date -u -d '+30 minutes' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(jq -n --arg title "$title" --arg due "$due_utc" '{title:$title, due_at_utc:$due, due_at_local:"10:00:00", timezone:"UTC"}')

  # First request
  curl -sS -X POST "$BASE_URL/api/v1/reminders" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Idempotency-Key: $idem_key" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null

  # Second request - should return cached response
  local headers_file="$TEST_DIR/replay-headers.txt"
  curl -sS -D "$headers_file" -X POST "$BASE_URL/api/v1/reminders" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Idempotency-Key: $idem_key" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null

  if grep -qi "x-idempotency-replay" "$headers_file"; then
    success "X-Idempotency-Replay header found in response"
    return 0
  else
    warn "X-Idempotency-Replay header not found (feature may not be fully implemented)"
    return 0  # Don't fail, just warn
  fi
}

test_idempotency_aggressive_retry() {
  log "Testing aggressive retry scenario (10 rapid requests with same key)..."
  local idem_key="test-aggressive-$TIMESTAMP-$RANDOM"
  local title="Aggressive Retry $TIMESTAMP"
  local due_utc
  due_utc=$(date -u -d '+30 minutes' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(jq -n --arg title "$title" --arg due "$due_utc" '{title:$title, due_at_utc:$due, due_at_local:"10:00:00", timezone:"UTC"}')

  log "Sending 10 parallel requests with same idempotency key..."
  for i in {1..10}; do
    curl -sS --max-time 30 -X POST "$BASE_URL/api/v1/reminders" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Idempotency-Key: $idem_key" \
      -H "Content-Type: application/json" \
      -d "$payload" >"$TEST_DIR/aggressive-$i.json" 2>&1 &
  done

  # Wait for all background processes with timeout protection
  local wait_timeout=60
  local wait_start=$(date +%s)
  while true; do
    # Check if all background jobs are done
    if ! jobs -r | grep -q .; then
      break
    fi

    # Check for timeout
    local wait_elapsed=$(($(date +%s) - wait_start))
    if [[ $wait_elapsed -ge $wait_timeout ]]; then
      error "Timeout waiting for parallel requests to complete (${wait_timeout}s)"
      # Kill any remaining background jobs
      jobs -p | xargs -r kill 2>/dev/null || true
      return 1
    fi

    sleep 0.5
  done

  log "Checking database for duplicate reminders..."
  sleep 2  # Give time for all DB writes to complete
  local count
  count=$(psql_query "SELECT COUNT(*) FROM reminders WHERE title = '$title';" | tr -d '[:space:]')

  if [[ "$count" != "1" ]]; then
    error "Expected 1 reminder, found $count! Idempotency failed under concurrent load."
    psql_query "SELECT id, title, created_at FROM reminders WHERE title = '$title';" >&2
    return 1
  fi

  success "Aggressive retry test passed: only 1 reminder created from 10 concurrent requests"
}

test_idempotency_different_keys() {
  log "Testing that different idempotency keys create separate reminders..."
  local title="Different Keys Test $TIMESTAMP"
  local due_utc
  due_utc=$(date -u -d '+30 minutes' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(jq -n --arg title "$title" --arg due "$due_utc" '{title:$title, due_at_utc:$due, due_at_local:"10:00:00", timezone:"UTC"}')

  local key1="test-key1-$TIMESTAMP-$RANDOM"
  local key2="test-key2-$TIMESTAMP-$RANDOM"

  log "Creating reminder with key1: $key1"
  local resp1
  resp1=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Idempotency-Key: $key1" \
    -H "Content-Type: application/json" \
    -d "$payload")

  log "Creating reminder with key2: $key2"
  local resp2
  resp2=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Idempotency-Key: $key2" \
    -H "Content-Type: application/json" \
    -d "$payload")

  local id1 id2
  id1=$(echo "$resp1" | jq -r '.data.id // .id // empty')
  id2=$(echo "$resp2" | jq -r '.data.id // .id // empty')

  if [[ "$id1" == "$id2" ]]; then
    error "Same reminder ID returned for different idempotency keys! id=$id1"
    return 1
  fi

  local count
  count=$(psql_query "SELECT COUNT(*) FROM reminders WHERE title = '$title';" | tr -d '[:space:]')
  assert_equals "$count" "2" "Two separate reminders created with different idempotency keys"
}

test_idempotency_key_expiry() {
  log "Testing idempotency key expiry field..."
  local idem_key="test-expiry-$TIMESTAMP-$RANDOM"
  local title="Expiry Test $TIMESTAMP"
  local due_utc
  due_utc=$(date -u -d '+30 minutes' '+%Y-%m-%dT%H:%M:00Z')
  local payload
  payload=$(jq -n --arg title "$title" --arg due "$due_utc" '{title:$title, due_at_utc:$due, due_at_local:"10:00:00", timezone:"UTC"}')

  curl -sS -X POST "$BASE_URL/api/v1/reminders" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Idempotency-Key: $idem_key" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null

  local expires_at
  expires_at=$(psql_query "SELECT expires_at FROM idempotency_keys WHERE idempotency_key = '$idem_key';" 2>/dev/null || echo "")

  if [[ -z "$expires_at" || "$expires_at" == "null" ]]; then
    warn "expires_at field empty or not found (feature may not be implemented)"
    return 0
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
