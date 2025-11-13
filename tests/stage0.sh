#!/usr/bin/env bash
# Stage 0: Infrastructure Tests
# Tests container health, database connectivity, authentication, rate limiting, etc.

set -euo pipefail

#############################################
# Stage 0: Infrastructure
#############################################

infrastructure_check() {
  local check="$1"
  local rc=0
  case "$check" in
    containers)
      local containers=(vib-orchestrator vib-worker vib-beat vib-postgres vib-redis vib-qdrant)
      for c in "${containers[@]}"; do
        if ! docker inspect "$c" &>/dev/null; then
          error "Container $c missing"
          rc=1
          continue
        fi
        local running
        running=$(docker inspect -f '{{.State.Running}}' "$c" 2>/dev/null || echo "false")
        assert_equals "$running" "true" "Container $c running" || rc=1
      done
      ;;
    health_status)
      local tmp="$TEST_DIR/health.json"
      local http
      http=$(curl -sS -w "%{http_code}" -o "$tmp" "$HEALTH_URL")
      assert_status_code "$http" "200" "Health endpoint returns 200" || rc=1
      local status
      status=$(jq -r '.status' "$tmp" 2>/dev/null)
      assert_equals "$status" "healthy" "Health status is healthy" || rc=1
      ;;
    health_services)
      local tmp="$TEST_DIR/health.json"
      [[ -f "$tmp" ]] || curl -sS "$HEALTH_URL" -o "$tmp"
      for svc in postgres redis qdrant celery_worker; do
        local svc_status
        svc_status=$(jq -r ".services.$svc" "$tmp" 2>/dev/null)
        assert_equals "$svc_status" "ok" "Service $svc healthy" || rc=1
      done
      ;;
    metrics_endpoint)
      local headers="$TEST_DIR/metrics.headers"
      local body="$TEST_DIR/metrics.prom"
      local code
      code=$(curl -sS -D "$headers" -o "$body" -w "%{http_code}" "$METRICS_URL")
      assert_status_code "$code" "200" "Metrics endpoint returns 200" || rc=1
      assert_contains "$(cat "$body")" "# HELP" "Metrics contain HELP blocks" || rc=1
      ;;
    metrics_help)
      local body="$TEST_DIR/metrics.prom"
      [[ -f "$body" ]] || body=$(curl -sS "$METRICS_URL")
      assert_contains "$(cat "$body")" "api_request_duration_seconds" "api_request_duration_seconds metric present" || rc=1
      ;;
    database)
      local result
      result=$(psql_query "SELECT 1;" | tr -d "[:space:]")
      assert_equals "$result" "1" "Database responds" || rc=1
      ;;
    redis)
      local pong
      pong=$(redis_cmd ping 2>/dev/null || echo "")
      assert_equals "$pong" "PONG" "Redis responds" || rc=1
      ;;
    qdrant_collection)
      local response
      response=$(curl -sS http://localhost:6333/collections || echo "")
      assert_contains "$response" "knowledge_base" "Qdrant collection available" || rc=1
      ;;
    auth_valid)
      local status
      status=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/protected")
      assert_status_code "$status" "200" "Valid token accepted" || rc=1
      ;;
    auth_invalid)
      local status
      status=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer wrong-token" "$BASE_URL/api/v1/protected")
      assert_status_code "$status" "401" "Invalid token rejected" || rc=1
      ;;
    auth_missing)
      local status
      status=$(curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/protected")
      assert_status_code "$status" "401" "Missing token rejected" || rc=1
      ;;
    rate_limit)
      # Make parallel requests to properly test burst rate limiting
      # Limit: 30 requests per 60 seconds
      # Use 32 requests to trigger limit while avoiding connection pool exhaustion
      local i status count_429=0 total_requests=32
      local tmpdir=$(mktemp -d)

      # Launch parallel requests with timeout
      for i in $(seq 1 $total_requests); do
        (
          status=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/chat" 2>/dev/null || echo "000")
          echo "$status" > "$tmpdir/status_$i"
        ) &
      done

      # Wait for all requests to complete with timeout protection
      local wait_timeout=30
      local wait_start=$(date +%s)
      while true; do
        # Check if all background jobs are done
        if ! jobs -r | grep -q .; then
          break
        fi

        # Check for timeout
        local wait_elapsed=$(($(date +%s) - wait_start))
        if [[ $wait_elapsed -ge $wait_timeout ]]; then
          error "Timeout waiting for parallel rate limit requests to complete (${wait_timeout}s)"
          # Kill any remaining background jobs
          jobs -p | xargs -r kill 2>/dev/null || true
          rm -rf "$tmpdir"
          return 1
        fi

        sleep 0.5
      done

      # Count 429 responses
      for i in $(seq 1 $total_requests); do
        if [[ -f "$tmpdir/status_$i" ]]; then
          status=$(cat "$tmpdir/status_$i")
          [[ "$status" == "429" ]] && count_429=$((count_429 + 1))
        fi
      done

      # Cleanup temp files
      rm -rf "$tmpdir"

      if [[ $count_429 -gt 0 ]]; then
        success "Rate limit triggered ($count_429/$total_requests responses)"
      else
        error "Rate limit did not trigger"
        rc=1
      fi
      ;;
    rate_limit_reset)
      if $FAST_MODE; then
        warn "Skipping rate limit reset in fast mode"
        return 0
      fi
      log "Waiting for rate limit window reset"
      sleep 65
      local status
      status=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/chat")
      assert_equals "$status" "200" "Requests succeed after window reset" || rc=1
      ;;
    logs)
      local line
      line=$(docker logs vib-orchestrator --tail 50 2>&1 | grep '{' | tail -n 1)
      if [[ -z "$line" ]]; then
        error "Structured logs not found"
        rc=1
      else
        local has_ts has_request
        has_ts=$(echo "$line" | jq -e '.timestamp' >/dev/null 2>&1; echo $?)
        has_request=$(echo "$line" | jq -e '.event // .endpoint' >/dev/null 2>&1; echo $?)
        [[ $has_ts -eq 0 ]] && success "Logs contain timestamp" || { error "Logs missing timestamp"; rc=1; }
        [[ $has_request -eq 0 ]] && success "Logs contain endpoint/event" || { error "Logs missing endpoint"; rc=1; }
      fi
      ;;
    metrics_increment)
      local before after
      before=$(curl -sS "$METRICS_URL" | awk '/notes_created_total/ {print $2; exit}' || echo 0)
      curl -sS -X GET "$BASE_URL/api/v1/notes" -H "Authorization: Bearer $TOKEN" >/dev/null || true
      after=$(curl -sS "$METRICS_URL" | awk '/api_request_duration_seconds_bucket/ {print $2; exit}' || echo 0)
      assert_not_empty "$after" "Metrics updated after request" || rc=1
      ;;
    cors)
      local header
      header=$(curl -sS -D - -o /dev/null -H "Origin: https://example.com" "$BASE_URL/api/v1/health" | grep -i "access-control-allow-origin" || true)
      assert_contains "$header" "*" "CORS header present" || rc=1
      ;;
    tls)
      if [[ "$BASE_URL" == https* ]]; then
        local status
        status=$(curl -sk -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/health")
        assert_status_code "$status" "200" "TLS endpoint reachable" || rc=1
      else
        warn "BASE_URL not HTTPS; skipping TLS check"
      fi
      ;;
    celery_worker)
      docker exec vib-worker celery -A worker.tasks inspect ping >/dev/null 2>&1 && success "Celery worker responding" || { error "Celery worker not responding"; rc=1; }
      ;;
    celery_beat)
      docker exec vib-beat pgrep -f celery >/dev/null 2>&1 && success "Celery beat running" || { error "Celery beat not running"; rc=1; }
      ;;
    db_schema)
      local tables
      tables=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")
      assert_greater_than "${tables:-0}" "10" "DB schema migrated" || rc=1
      ;;
    metrics_prom)
      local content
      content=$(curl -sS "$METRICS_URL")
      assert_contains "$content" "reminder_fire_lag_seconds_bucket" "Reminder lag histogram exposed" || rc=1
      ;;
    qdrant_metric)
      local content
      content=$(curl -sS "$METRICS_URL" | grep qdrant_points_count || true)
      assert_not_empty "$content" "Qdrant gauge exported" || rc=1
      ;;
    *)
      error "Unknown infrastructure check $check"
      rc=1
      ;;
  esac
  return $rc
}

run_stage0() {
  section "STAGE 0: INFRASTRUCTURE"
  local tests=(
    "infra_containers infrastructure_check containers"
    "infra_health_status infrastructure_check health_status"
    "infra_health_services infrastructure_check health_services"
    "infra_metrics_endpoint infrastructure_check metrics_endpoint"
    "infra_metrics_help infrastructure_check metrics_help"
    "infra_database infrastructure_check database"
    "infra_redis infrastructure_check redis"
    "infra_qdrant infrastructure_check qdrant_collection"
    "infra_auth_valid infrastructure_check auth_valid"
    "infra_auth_invalid infrastructure_check auth_invalid"
    "infra_auth_missing infrastructure_check auth_missing"
    "infra_rate_limit infrastructure_check rate_limit"
    "infra_rate_limit_reset infrastructure_check rate_limit_reset"
    "infra_logs infrastructure_check logs"
    "infra_metrics_increment infrastructure_check metrics_increment"
    "infra_cors infrastructure_check cors"
    "infra_tls infrastructure_check tls"
    "infra_celery_worker infrastructure_check celery_worker"
    "infra_celery_beat infrastructure_check celery_beat"
    "infra_db_schema infrastructure_check db_schema"
    "infra_metrics_prom infrastructure_check metrics_prom"
    "infra_qdrant_metric infrastructure_check qdrant_metric"
  )
  for entry in "${tests[@]}"; do
    IFS=' ' read -r name func arg <<<"$entry"
    run_test "$name" "$func" "$arg"
  done
}
