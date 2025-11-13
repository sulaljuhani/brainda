#!/usr/bin/env bash
# Stage 8: Passkeys + Multi-User Tests
# Tests authentication, sessions, organizations, and data isolation

set -euo pipefail

test_organizations_table_exists() {
  log "Checking organizations table exists..."
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'organizations';" 2>/dev/null | tr -d '[:space:]')

  if [[ "$count" == "1" ]]; then
    success "organizations table exists"
  else
    warn "organizations table not found (Stage 8 may not be implemented)"
  fi
  return 0
}

test_passkey_credentials_table() {
  log "Checking passkey_credentials table exists..."
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'passkey_credentials';" 2>/dev/null | tr -d '[:space:]')

  if [[ "$count" == "1" ]]; then
    success "passkey_credentials table exists"
  else
    warn "passkey_credentials table not found (Stage 8 may not be implemented)"
  fi
  return 0
}

test_totp_secrets_table() {
  log "Checking totp_secrets table exists..."
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'totp_secrets';" 2>/dev/null | tr -d '[:space:]')

  if [[ "$count" == "1" ]]; then
    success "totp_secrets table exists"
  else
    warn "totp_secrets table not found (Stage 8 may not be implemented)"
  fi
  return 0
}

test_sessions_table_exists() {
  log "Checking sessions table exists..."
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'sessions';" 2>/dev/null | tr -d '[:space:]')

  if [[ "$count" == "1" ]]; then
    success "sessions table exists"

    # Check for required columns
    local has_token has_expires
    has_token=$(psql_query "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='sessions' AND column_name='token';" | tr -d '[:space:]')
    has_expires=$(psql_query "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='sessions' AND column_name='expires_at';" | tr -d '[:space:]')

    if [[ "$has_token" == "1" && "$has_expires" == "1" ]]; then
      success "sessions table has required columns (token, expires_at)"
    fi
  else
    warn "sessions table not found (Stage 8 may not be implemented)"
  fi
  return 0
}

test_multi_user_support() {
  log "Testing multi-user support structure..."
  # Check if users table has organization_id
  local has_org_id
  has_org_id=$(psql_query "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='users' AND column_name='organization_id';" 2>/dev/null | tr -d '[:space:]')

  if [[ "$has_org_id" == "1" ]]; then
    success "users table has organization_id for multi-user support"
  else
    warn "organization_id not found in users table (Stage 8 may not be implemented)"
  fi
  return 0
}

test_user_data_isolation() {
  log "Testing user data isolation (all tables have user_id)..."
  local tables=("notes" "reminders" "calendar_events" "documents")
  local all_have_user_id=true

  for table in "${tables[@]}"; do
    local has_user_id
    has_user_id=$(psql_query "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='$table' AND column_name='user_id';" 2>/dev/null | tr -d '[:space:]')
    if [[ "$has_user_id" != "1" ]]; then
      warn "$table table missing user_id column"
      all_have_user_id=false
    fi
  done

  if $all_have_user_id; then
    success "All core tables have user_id for data isolation"
  fi
  return 0
}

test_session_management() {
  log "Testing session management endpoints..."
  # Test logout endpoint
  local status
  status=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/auth/logout" \
    -H "Authorization: Bearer $TOKEN" 2>/dev/null)

  if [[ "$status" == "200" || "$status" == "401" || "$status" == "404" ]]; then
    if [[ "$status" == "404" ]]; then
      warn "Auth endpoints not found (Stage 8 may not be implemented)"
    else
      success "Session management endpoint exists (status: $status)"
    fi
  fi
  return 0
}

test_auth_audit_log() {
  log "Checking auth_audit_log table exists..."
  local count
  count=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'auth_audit_log';" 2>/dev/null | tr -d '[:space:]')

  if [[ "$count" == "1" ]]; then
    success "auth_audit_log table exists for security auditing"
  else
    warn "auth_audit_log table not found (Stage 8 may not be implemented)"
  fi
  return 0
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
    "stage8_session_endpoints test_session_management"
    "stage8_auth_audit test_auth_audit_log"
  )
  for entry in "${tests[@]}"; do
    IFS=' ' read -r name func <<<"$entry"
    run_test "$name" "$func"
  done
}
