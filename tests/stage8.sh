#!/usr/bin/env bash
# Stage 8: Passkeys + Multi-User Tests
# Tests authentication, sessions, organizations, and data isolation

set -euo pipefail
IFS=$'\n\t'

CURRENT_USER_ID=""
TOTP_SECRET=""
API_LAST_STATUS=""
API_LAST_BODY=""

assert_table_exists() {
  local table="$1"
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name = '$table';" | tr -d '[:space:]')
  assert_equals "$count" "1" "Table '$table' exists"
}

assert_column_exists() {
  local table="$1"
  local column="$2"
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='$table' AND column_name='$column';" | tr -d '[:space:]')
  assert_equals "$count" "1" "Column $table.$column exists"
}

assert_foreign_key() {
  local table="$1"
  local column="$2"
  local referenced_table="$3"
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.constraint_schema = kcu.constraint_schema JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name AND ccu.constraint_schema = tc.constraint_schema WHERE tc.table_schema='public' AND tc.constraint_type='FOREIGN KEY' AND tc.table_name='$table' AND kcu.column_name='$column' AND ccu.table_name='$referenced_table';" | tr -d '[:space:]')
  assert_equals "$count" "1" "Foreign key $table.$column references $referenced_table"
}

api_post() {
  local url="$1"
  local data="$2"
  shift 2 || true
  local tmp
  tmp=$(mktemp)
  local status
  status=$(curl -sS -o "$tmp" -w "%{http_code}" -X POST "$url" "$@" -d "$data")
  API_LAST_STATUS="$status"
  API_LAST_BODY=$(cat "$tmp")
  rm -f "$tmp"
}

require_api_token() {
  if [[ -z "${TOKEN:-}" ]]; then
    error "API token (TOKEN) is required for Stage 8 auth tests"
    return 1
  fi
}

ensure_test_user_id() {
  if [[ -n "$CURRENT_USER_ID" ]]; then
    return 0
  fi
  require_api_token || return 1
  CURRENT_USER_ID=$(psql_query "SELECT id FROM users WHERE api_token = '$TOKEN' LIMIT 1;" | tr -d '[:space:]')
  assert_not_empty "$CURRENT_USER_ID" "Resolved test user from API token"
}

generate_totp_code() {
  local secret="$1"
  python3 - "$secret" <<'PY'
import base64
import hashlib
import hmac
import struct
import sys
import time

secret = sys.argv[1].strip().replace(' ', '')
if not secret:
    print("")
    sys.exit(0)

padding = '=' * (-len(secret) % 8)
key = base64.b32decode(secret.upper() + padding)
interval = 30
counter = int(time.time()) // interval
msg = struct.pack('>Q', counter)
digest = hmac.new(key, msg, hashlib.sha1).digest()
offset = digest[-1] & 0x0F
code = (int.from_bytes(digest[offset:offset+4], 'big') & 0x7FFFFFFF) % 1000000
print(f"{code:06d}")
PY
}

ensure_totp_secret_enabled() {
  ensure_test_user_id || return 1
  log "Ensuring TOTP secret is configured and verified"
  local headers=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")
  api_post "$BASE_URL/api/v1/auth/totp/setup" '{}' "${headers[@]}"
  assert_equals "$API_LAST_STATUS" "200" "TOTP setup endpoint available"
  local secret
  secret=$(echo "$API_LAST_BODY" | jq -r '.secret // empty')
  assert_not_empty "$secret" "Received TOTP secret"
  TOTP_SECRET="$secret"

  local code
  code=$(generate_totp_code "$TOTP_SECRET")
  assert_not_empty "$code" "Generated current TOTP code"
  local verify_payload
  verify_payload=$(jq -n --arg code "$code" '{code:$code}')
  api_post "$BASE_URL/api/v1/auth/totp/verify" "$verify_payload" "${headers[@]}"
  assert_equals "$API_LAST_STATUS" "200" "TOTP verify endpoint succeeded"
  local success_flag
  success_flag=$(echo "$API_LAST_BODY" | jq -r '.success // false')
  assert_equals "$success_flag" "true" "TOTP verification accepted code"

  local enabled
  enabled=$(psql_query "SELECT enabled FROM totp_secrets WHERE user_id = '$CURRENT_USER_ID';" | tr -d '[:space:]')
  assert_equals "$enabled" "t" "TOTP secret marked enabled in database"
}

test_organizations_table_exists() {
  log "Validating organizations schema"
  assert_table_exists "organizations"
  assert_column_exists "organizations" "id"
  assert_column_exists "organizations" "name"
  assert_column_exists "organizations" "created_at"
}

test_passkey_credentials_table() {
  log "Validating passkey credential schema"
  assert_table_exists "passkey_credentials"
  assert_column_exists "passkey_credentials" "user_id"
  assert_column_exists "passkey_credentials" "credential_id"
  assert_column_exists "passkey_credentials" "public_key"
  assert_column_exists "passkey_credentials" "counter"
  assert_foreign_key "passkey_credentials" "user_id" "users"
}

test_totp_secrets_table() {
  log "Validating TOTP secret storage"
  assert_table_exists "totp_secrets"
  assert_column_exists "totp_secrets" "user_id"
  assert_column_exists "totp_secrets" "secret"
  assert_column_exists "totp_secrets" "backup_codes"
  assert_column_exists "totp_secrets" "enabled"
  assert_foreign_key "totp_secrets" "user_id" "users"
}

test_sessions_table_exists() {
  log "Validating sessions schema"
  assert_table_exists "sessions"
  assert_column_exists "sessions" "token"
  assert_column_exists "sessions" "user_id"
  assert_column_exists "sessions" "device_type"
  assert_column_exists "sessions" "expires_at"
  assert_column_exists "sessions" "created_at"
  assert_foreign_key "sessions" "user_id" "users"
}

test_multi_user_support() {
  log "Validating multi-tenant relationships"
  assert_column_exists "users" "organization_id"
  assert_foreign_key "users" "organization_id" "organizations"
}

test_user_data_isolation() {
  log "Checking user ownership constraints on core tables"
  local tables=("notes" "reminders" "calendar_events" "documents")
  for table in "${tables[@]}"; do
    assert_column_exists "$table" "user_id"
    assert_foreign_key "$table" "user_id" "users"
  done
}

test_totp_flow() {
  log "Exercising TOTP setup and verification endpoints"
  ensure_totp_secret_enabled
  success "TOTP setup + verification completed"
}

test_session_management() {
  log "Testing session creation via TOTP and logout invalidation"
  ensure_totp_secret_enabled
  local code
  code=$(generate_totp_code "$TOTP_SECRET")
  assert_not_empty "$code" "Generated TOTP code for authentication"
  local payload
  payload=$(jq -n --arg user_id "$CURRENT_USER_ID" --arg code "$code" '{user_id:$user_id, code:$code}')
  api_post "$BASE_URL/api/v1/auth/totp/authenticate" "$payload" -H "Content-Type: application/json"
  assert_equals "$API_LAST_STATUS" "200" "TOTP authenticate endpoint returned 200"
  local session_token
  session_token=$(echo "$API_LAST_BODY" | jq -r '.session_token // empty')
  assert_not_empty "$session_token" "Received session token"

  local db_count
  db_count=$(psql_query "SELECT COUNT(*) FROM sessions WHERE token = '$session_token';" | tr -d '[:space:]')
  assert_equals "$db_count" "1" "Session persisted in database"

  api_post "$BASE_URL/api/v1/auth/logout" '{}' -H "Authorization: Bearer $session_token" -H "Content-Type: application/json"
  assert_equals "$API_LAST_STATUS" "200" "Logout endpoint invalidated session"

  local post_logout_count
  post_logout_count=$(psql_query "SELECT COUNT(*) FROM sessions WHERE token = '$session_token';" | tr -d '[:space:]')
  assert_equals "$post_logout_count" "0" "Session removed after logout"
}

test_auth_audit_log() {
  log "Validating auth audit log schema"
  assert_table_exists "auth_audit_log"
  assert_column_exists "auth_audit_log" "user_id"
  assert_column_exists "auth_audit_log" "event_type"
  assert_column_exists "auth_audit_log" "created_at"
}

run_stage8() {
  section "STAGE 8: PASSKEYS + MULTI-USER"
  local tests=(
    "stage8_org_table test_organizations_table_exists"
    "stage8_passkey_table test_passkey_credentials_table"
    "stage8_totp_table test_totp_secrets_table"
    "stage8_sessions_table test_sessions_table_exists"
    "stage8_multi_user test_multi_user_support"
    "stage8_user_isolation test_user_data_isolation"
    "stage8_totp_flow test_totp_flow"
    "stage8_session_endpoints test_session_management"
    "stage8_auth_audit test_auth_audit_log"
  )
  for entry in "${tests[@]}"; do
    IFS=' ' read -r name func <<<"$entry"
    run_test "$name" "$func"
  done
}
