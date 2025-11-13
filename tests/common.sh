#!/usr/bin/env bash
# common.sh
# Common functions, variables, and fixtures for VIB integration tests
# This file is sourced by stage test scripts and the test runner

set -euo pipefail
IFS=$'\n\t'

# These will be set by the test runner before sourcing
# SCRIPT_ROOT, TIMESTAMP, START_TIME, TEST_DIR, etc.

# Global variables (can be overridden by test runner)
BASE_URL="${BASE_URL:-http://localhost:8000}"
HEALTH_URL="$BASE_URL/api/v1/health"
METRICS_URL="$BASE_URL/api/v1/metrics"
TOKEN="${API_TOKEN:-}"
CONFIG_FILE="${TEST_CONFIG:-test-config.json}"
RUN_STAGE="${RUN_STAGE:-}"
FAST_MODE="${FAST_MODE:-false}"
HTML_REPORT="${HTML_REPORT:-false}"
VERBOSE="${VERBOSE:-false}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"

TOTAL_TESTS="${TOTAL_TESTS:-0}"
PASSED_TESTS="${PASSED_TESTS:-0}"
FAILED_TESTS="${FAILED_TESTS:-0}"
WARNINGS="${WARNINGS:-0}"
declare -a FAILED_TEST_NAMES=()
declare -a TEST_RECORDS=()
LAST_TEST_DURATION=0

API_LATENCY_THRESHOLD=${API_LATENCY_THRESHOLD:-500}
SEARCH_LATENCY_THRESHOLD=${SEARCH_LATENCY_THRESHOLD:-200}
REMINDER_FIRE_LAG_TARGET=${REMINDER_FIRE_LAG_TARGET:-5}
PUSH_SUCCESS_TARGET=${PUSH_SUCCESS_TARGET:-0.98}
DOC_INGESTION_TARGET=${DOC_INGESTION_TARGET:-120}
CONCURRENT_REQUEST_THRESHOLD=${CONCURRENT_REQUEST_THRESHOLD:-0}

REMINDER_FIRE_LAG_P95="unknown"
PUSH_SUCCESS_RATE="unknown"
DOC_INGESTION_P95="unknown"
VECTOR_SEARCH_P95="unknown"

declare -A SKIP_TEST_MAP=()
declare -A SLOW_TEST_MAP=(
  [reminder_fires]=1
  [metrics_fire_lag]=1
  [document_processing_speed]=1
  [document_20_page_slo]=1
  [backup_verification]=1
  [workflow_backup_restore]=1
)

HAS_BC=false
HAS_PYTHON=false
if command -v bc >/dev/null 2>&1; then
  HAS_BC=true
fi
if command -v python3 >/dev/null 2>&1; then
  HAS_PYTHON=true
fi
if [[ "$HAS_BC" == false && "$HAS_PYTHON" == false ]]; then
  echo "[ERROR] Missing dependency: need 'python3' (or install 'bc') for numeric comparisons" >&2
  exit 1
fi

float_greater_than() {
  local left="$1"
  local right="$2"

  if [[ "$HAS_BC" == true ]]; then
    local result
    result=$(echo "$left > $right" | bc -l)
    [[ "$result" == "1" ]]
  else
    python3 - "$left" "$right" <<'PY'
import sys
left=float(sys.argv[1])
right=float(sys.argv[2])
sys.exit(0 if left > right else 1)
PY
  fi
}

float_less_than() {
  local left="$1"
  local right="$2"

  if [[ "$HAS_BC" == true ]]; then
    local result
    result=$(echo "$left < $right" | bc -l)
    [[ "$result" == "1" ]]
  else
    python3 - "$left" "$right" <<'PY'
import sys
left=float(sys.argv[1])
right=float(sys.argv[2])
sys.exit(0 if left < right else 1)
PY
  fi
}

# Logging helpers
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
  echo "[$(date '+%H:%M:%S')] $1"
}

success() {
  echo -e "${GREEN}[$(date '+%H:%M:%S')] ✓ $1${NC}"
}

error() {
  echo -e "${RED}[$(date '+%H:%M:%S')] ✗ $1${NC}" >&2
}

warn() {
  echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠ $1${NC}"
  WARNINGS=$((WARNINGS + 1))
}

section() {
  echo ""
  echo "======================================"
  echo "$1"
  echo "======================================"
  echo ""
}

# Assertion helpers
assert_equals() {
  local actual="$1"
  local expected="$2"
  local message="$3"
  if [[ "$actual" == "$expected" ]]; then
    success "$message (expected=$expected, actual=$actual)"
    return 0
  else
    error "$message (expected=$expected, actual=$actual)"
    return 1
  fi
}

assert_not_empty() {
  local value="$1"
  local message="$2"
  if [[ -n "$value" && "$value" != "null" ]]; then
    success "$message"
    return 0
  else
    error "$message (value empty)"
    return 1
  fi
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  local message="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    success "$message"
    return 0
  else
    error "$message (missing '$needle')"
    return 1
  fi
}

assert_greater_than() {
  local actual="$1"
  local expected="$2"
  local message="$3"
  if float_greater_than "$actual" "$expected"; then
    success "$message ($actual > $expected)"
    return 0
  else
    error "$message ($actual <= $expected)"
    return 1
  fi
}

assert_less_than() {
  local actual="$1"
  local expected="$2"
  local message="$3"
  if float_less_than "$actual" "$expected"; then
    success "$message ($actual < $expected)"
    return 0
  else
    error "$message ($actual >= $expected)"
    return 1
  fi
}

assert_file_exists() {
  local file="$1"
  local message="$2"
  if [[ -f "$file" ]]; then
    success "$message"
    return 0
  else
    error "$message (missing $file)"
    return 1
  fi
}

assert_status_code() {
  local actual="$1"
  local expected="$2"
  local message="$3"
  if [[ "$actual" == "$expected" ]]; then
    success "$message"
    return 0
  else
    error "$message (expected $expected, got $actual)"
    return 1
  fi
}

assert_json_field() {
  local json="$1"
  local jq_expr="$2"
  local expected="$3"
  local message="$4"
  local value
  value=$(echo "$json" | jq -r "$jq_expr" 2>/dev/null || echo "")
  if [[ -z "$expected" ]]; then
    assert_not_empty "$value" "$message"
  else
    assert_equals "$value" "$expected" "$message"
  fi
}

# Wait helper
wait_for() {
  local condition="$1"
  local timeout="$2"
  local description="$3"
  local waited=0
  log "Waiting for: $description (timeout ${timeout}s)"
  while [[ $waited -lt $timeout ]]; do
      if eval "$condition"; then
          success "Condition met after ${waited}s"
          return 0
      fi
      sleep 1
      waited=$((waited + 1))
  done
  error "Timeout waiting for: $description"
  return 1
}

measure_latency() {
  local endpoint="$1"
  local iterations="$2"
  local results=()
  for ((i=0; i<iterations; i++)); do
    local start end duration
    start=$(date +%s%3N)
    curl -sS ${VERBOSE:+-v} -H "Authorization: Bearer $TOKEN" "$BASE_URL$endpoint" >/dev/null
    end=$(date +%s%3N)
    duration=$((end - start))
    results+=($duration)
    sleep 0.1
  done
  printf '%s\n' "${results[@]}" | sort -n | awk -v p=95 'NR==1{count=0} {arr[NR]=$1} END {if (NR==0) {print 0; exit}; idx=int((p/100)*NR); if (idx<1) idx=1; if (idx>NR) idx=NR; print arr[idx]}'
}

histogram_quantile_from_metrics() {
  if [[ -z "${METRIC_NAME:-}" || -z "${METRIC_QUANTILE:-}" ]]; then
    echo "nan"
    return 0
  fi
  python - <<'PY'
import os, sys

metric = os.environ.get('METRIC_NAME')
try:
    quantile = float(os.environ.get('METRIC_QUANTILE', '0.95'))
except (TypeError, ValueError):
    print('nan')
    sys.exit(0)

if not metric:
    print('nan')
    sys.exit(0)

lines = sys.stdin.read().strip().splitlines()
buckets = []
for line in lines:
    if not line.startswith(metric + '_bucket'):
        continue
    try:
        parts = line.split('le="')[1]
        le = parts.split('"')[0]
        value = float(line.split(' ')[-1])
        if le == '+Inf':
            continue
        buckets.append((float(le), value))
    except Exception:
        pass
if not buckets:
    print('nan')
    sys.exit(0)
buckets.sort(key=lambda x: x[0])
total = buckets[-1][1]
if total == 0:
    print('0')
    sys.exit(0)
threshold = total * quantile
prev_count = 0
prev_bound = 0.0
for bound, count in buckets:
    if count >= threshold:
        # simple linear interpolation
        bucket_count = count - prev_count
        if bucket_count <= 0:
            print(str(bound))
            sys.exit(0)
        fraction = (threshold - prev_count) / bucket_count
        estimate = prev_bound + (bound - prev_bound) * fraction
        print(f"{estimate:.3f}")
        sys.exit(0)
    prev_count = count
    prev_bound = bound
print(str(buckets[-1][0]))
PY
}

# Command wrappers
psql_query() {
  local sql="$1"
  local user="${POSTGRES_USER:-vib}"
  local db="${POSTGRES_DB:-vib}"
  docker exec vib-postgres psql -U "$user" -d "$db" -At -c "$sql"
}

redis_cmd() {
  docker exec vib-redis redis-cli "$@"
}

compose_cmd() {
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    docker compose "$@"
  fi
}

# Internal helper to track execution duration without duplicating logic across
# different runners (standard vs retry).
_execute_test_func() {
  local test_func="$1"
  shift
  local start_ts end_ts rc=0
  start_ts=$(date +%s)
  if "$test_func" "$@"; then
    rc=0
  else
    rc=$?
  fi
  end_ts=$(date +%s)
  LAST_TEST_DURATION=$((end_ts - start_ts))
  return $rc
}

# Test framework
run_test() {
  local test_name="$1"
  local test_func="$2"
  shift 2
  local test_args=("$@")

  if [[ -n "$RUN_STAGE" && "$test_name" != "$RUN_STAGE" && "$RUN_STAGE" =~ ^[0-9]+$ ]]; then
    # stage filtering handled outside; do nothing here
    :
  fi

  if [[ -n "${SKIP_TEST_MAP[$test_name]:-}" ]]; then
    warn "Skipping $test_name (per config)"
    TEST_RECORDS+=("$test_name|SKIPPED|0s|Skipped per config")
    return 0
  fi

  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  log "Running test: $test_name"
  local rc=0 duration=0
  if _execute_test_func "$test_func" "${test_args[@]}"; then
    rc=0
  else
    rc=$?
  fi
  duration=$LAST_TEST_DURATION
  if [[ $rc -eq 0 ]]; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
    success "$test_name passed (${duration}s)"
    TEST_RECORDS+=("$test_name|PASS|${duration}s|")
  else
    FAILED_TESTS=$((FAILED_TESTS + 1))
    FAILED_TEST_NAMES+=("$test_name")
    error "$test_name failed"
    TEST_RECORDS+=("$test_name|FAIL|${duration}s|see log")
  fi
  return $rc
}

run_test_with_retry() {
  local test_name="$1"
  local test_func="$2"
  local max_attempts=3
  local attempt=1
  shift 2
  local args=("$@")
  if [[ -n "${SKIP_TEST_MAP[$test_name]:-}" ]]; then
    warn "Skipping $test_name (per config)"
    TEST_RECORDS+=("$test_name|SKIPPED|0s|Skipped per config")
    return 0
  fi

  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  local rc=1
  local overall_start overall_end duration
  overall_start=$(date +%s)
  while [[ $attempt -le $max_attempts ]]; do
    log "Running test: $test_name (attempt $attempt/$max_attempts)"
    if _execute_test_func "$test_func" "${args[@]}"; then
      rc=0
      break
    fi
    rc=$?
    if [[ $attempt -lt $max_attempts ]]; then
      warn "$test_name attempt $attempt failed (rc=$rc). Retrying..."
      sleep 5
    fi
    attempt=$((attempt + 1))
  done
  overall_end=$(date +%s)
  duration=$((overall_end - overall_start))

  if [[ $rc -eq 0 ]]; then
    PASSED_TESTS=$((PASSED_TESTS + 1))
    success "$test_name passed (${duration}s, attempt $attempt/$max_attempts)"
    TEST_RECORDS+=("$test_name|PASS|${duration}s|${attempt} attempt(s)")
  else
    FAILED_TESTS=$((FAILED_TESTS + 1))
    FAILED_TEST_NAMES+=("$test_name")
    error "$test_name failed after $max_attempts attempt(s)"
    TEST_RECORDS+=("$test_name|FAIL|${duration}s|exhausted retries")
  fi
  return $rc
}

# Configuration loaders
load_env_file() {
  if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
    TOKEN=${API_TOKEN:-$TOKEN}
  fi
}

load_config_json() {
  if [[ -f "$CONFIG_FILE" ]]; then
    log "Loading config from $CONFIG_FILE"
    BASE_URL=$(jq -r '.base_url // empty' "$CONFIG_FILE" || echo "$BASE_URL")
    local configured_health_timeout
    configured_health_timeout=$(jq -r '.timeout.health_check // empty' "$CONFIG_FILE" || true)
    if [[ -n "$configured_health_timeout" && "$configured_health_timeout" != "null" ]]; then
      HEALTH_TIMEOUT="$configured_health_timeout"
    fi
    local skip_list
    mapfile -t skip_list < <(jq -r '.skip_tests[]?' "$CONFIG_FILE")
    for name in "${skip_list[@]}"; do
      [[ -n "$name" ]] && SKIP_TEST_MAP[$name]=1
    done
    local custom_token
    custom_token=$(jq -r '.token // empty' "$CONFIG_FILE" || true)
    if [[ -n "$custom_token" && "$custom_token" != "null" ]]; then
      TOKEN="$custom_token"
    fi
  fi
}

ensure_prereqs() {
  for bin in curl jq docker; do
    if ! command -v "$bin" >/dev/null 2>&1; then
      error "Missing dependency: $bin"
      exit 1
    fi
  done

  if [[ "$HAS_BC" == false && "$HAS_PYTHON" == false ]]; then
    error "Missing dependency: need 'python3' or 'bc'"
    exit 1
  fi
}

# Fixture state
NOTE_FIXTURE_CREATED=false
NOTE_FIXTURE_TITLE="MVP Test Note $TIMESTAMP"
NOTE_FIXTURE_ID=""
NOTE_FIXTURE_MD_PATH=""
NOTE_FIXTURE_BODY="This is an automated integration test note generated at $TIMESTAMP about the assistant experience"
NOTE_DEDUP_RESPONSE=""
SPECIAL_NOTE_ID=""
SPECIAL_NOTE_PATH=""
CHAT_NOTE_ID=""

REMINDER_FIXTURE_CREATED=false
REMINDER_ID=""
REMINDER_FIRE_ID=""
REMINDER_DUE_UTC=""
REMINDER_DUE_LOCAL=""
DEVICE_ID=""
RECURRENCE_IDS=()

DOC_FIXTURE_CREATED=false
DOC_ID=""
DOC_JOB_ID=""
DOC_FILENAME="test-document.pdf"
DOC_CHUNK_COUNT=0
DOC_LARGE_ID=""
DOC_LARGE_JOB_ID=""
DOC_LARGE_FILENAME="test-document-large.pdf"
DOC_TWENTY_ID=""
DOC_TWENTY_JOB_ID=""
DOC_FAILED_ID=""
DOC_FAILED_JOB_ID=""
DOC_DELETE_ID=""
DOC_DELETE_JOB_ID=""
declare -a DOC_CONCURRENT_IDS=()
LAST_JOB_ERROR=""
BACKUP_ROOT="${BACKUP_ROOT:-$SCRIPT_ROOT/backups/data}"
LATEST_BACKUP_TS=""

BACKUP_LAST_TIMESTAMP=""

TEST_USER_ID=""

CALENDAR_EVENT_ID=""

# Fixture helpers
get_test_user_id() {
  if [[ -n "$TEST_USER_ID" ]]; then
    echo "$TEST_USER_ID"
    return
  fi
  TEST_USER_ID=$(psql_query "SELECT id FROM users LIMIT 1;")
  echo "$TEST_USER_ID"
}

ensure_note_fixture() {
  if $NOTE_FIXTURE_CREATED; then
    return
  fi
  local payload
  payload=$(jq -n --arg title "$NOTE_FIXTURE_TITLE" --arg body "$NOTE_FIXTURE_BODY" '{title:$title, body:$body, tags:["integration","mvp"]}')
  local response
  response=$(curl -sS -X POST "$BASE_URL/api/v1/notes" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  NOTE_FIXTURE_ID=$(echo "$response" | jq -r '.data.id // .data["id"]')
  NOTE_FIXTURE_MD_PATH=$(echo "$response" | jq -r '.data.md_path')
  NOTE_DEDUP_RESPONSE=$(curl -sS -X POST "$BASE_URL/api/v1/notes" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  NOTE_FIXTURE_CREATED=true
}

ensure_special_title_notes() {
  if [[ -n "$SPECIAL_NOTE_ID" ]]; then
    return
  fi
  local response slug_title
  slug_title="Simple Slug Title $TIMESTAMP"
  response=$(curl -sS -X POST "$BASE_URL/api/v1/notes" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"title\":\"$slug_title\",\"body\":\"slug test\"}")
  SPECIAL_NOTE_ID=$(echo "$response" | jq -r '.data.id')
  SPECIAL_NOTE_PATH=$(echo "$response" | jq -r '.data.md_path')
}

ensure_reminder_fixture() {
  if $REMINDER_FIXTURE_CREATED; then
    return
  fi
  REMINDER_DUE_UTC=$(date -u -d '+30 minutes' '+%Y-%m-%dT%H:%M:00Z')
  REMINDER_DUE_LOCAL=$(date -d '+30 minutes' '+%H:%M:00')
  local payload response
  payload=$(jq -n --arg title "MVP Test Reminder $TIMESTAMP" --arg body "Reminder body" --arg due "$REMINDER_DUE_UTC" --arg local "$REMINDER_DUE_LOCAL" '{title:$title, body:$body, due_at_utc:$due, due_at_local:$local, timezone:"UTC"}')
  response=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  REMINDER_ID=$(echo "$response" | jq -r '.data.id')
  REMINDER_FIXTURE_CREATED=true
}

ensure_device_registered() {
  if [[ -n "$DEVICE_ID" ]]; then
    return
  fi
  local payload response
  payload=$(jq -n '{platform:"web", push_token:"testauth:testkey", push_endpoint:"https://example.com/push"}')
  response=$(curl -sS -X POST "$BASE_URL/api/v1/devices/register" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  DEVICE_ID=$(echo "$response" | jq -r '.device_id // .data.device_id')
}

ensure_document_fixture() {
  if $DOC_FIXTURE_CREATED; then
    return
  fi
  mkdir -p tests/fixtures
  if [[ ! -f tests/fixtures/$DOC_FILENAME ]]; then
    log "Creating test document fixture"
    python - <<'PY'
from pathlib import Path

def pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

text = """VIB integration test document for Stage 3+ verification.

This knowledge base document is generated automatically by the test harness.
It contains multiple paragraphs to trigger chunking and embedding.

Features referenced:
- Document ingestion
- Chunk creation
- Vector search
- RAG answer generation
- Knowledge base coverage
"""
escaped = pdf_escape(text.replace("\n", "\\n"))
stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET\n".encode("utf-8")

objects = []
objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
objects.append(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n")
objects.append(b"4 0 obj\n<< /Length " + str(len(stream)).encode("utf-8") + b" >>\nstream\n" + stream + b"endstream\nendobj\n")
objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

header = b"%PDF-1.4\n"
offsets = [0]
body = bytearray()
offset = len(header)
for obj in objects:
    offsets.append(offset)
    body.extend(obj)
    offset += len(obj)

xref_offset = len(header) + len(body)
xref_entries = ["0000000000 65535 f "]
for off in offsets[1:]:
    xref_entries.append(f"{off:010d} 00000 n ")
xref = "xref\n0 {count}\n".format(count=len(offsets)).encode("utf-8")
xref += ("\n".join(xref_entries) + "\n").encode("utf-8")
trailer = f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("utf-8")

output = Path("tests/fixtures/test-document.pdf")
output.parent.mkdir(parents=True, exist_ok=True)
with output.open("wb") as f:
    f.write(header)
    f.write(body)
    f.write(xref)
    f.write(trailer)
PY
  fi || true
  if [[ ! -f tests/fixtures/$DOC_FILENAME ]]; then
    # fallback simple text to pdf conversion
    printf 'VIB integration test document\n' > tests/fixtures/test-document.txt
    python - <<'PY'
from pathlib import Path
text = Path('tests/fixtures/test-document.txt').read_text()
from fpdf import FPDF
pdf = FPDF()
pdf.add_page()
pdf.set_font('Arial', size=12)
for line in text.split('\n'):
    pdf.cell(0, 10, txt=line, ln=True)
pdf.output('tests/fixtures/test-document.pdf')
PY
  fi || true
  local response tmp_file http_status
  tmp_file=$(mktemp)
  http_status=$(curl -sS -o "$tmp_file" -w "%{http_code}" -X POST \
    "$BASE_URL/api/v1/ingest" -H "Authorization: Bearer $TOKEN" \
    -F "file=@tests/fixtures/$DOC_FILENAME")
  response=$(cat "$tmp_file")
  rm -f "$tmp_file"
  if [[ $http_status -lt 200 || $http_status -ge 300 ]]; then
    error "Document ingestion failed with status $http_status: $response"
    return 1
  fi
  DOC_ID=$(echo "$response" | jq -r '.document_id // .data.document_id')
  DOC_JOB_ID=$(echo "$response" | jq -r '.job_id')
  if [[ -z "$DOC_ID" || "$DOC_ID" == "null" ]]; then
    error "Document ingestion did not return a document_id. Response: $response"
    return 1
  fi
  log "Document ingestion request succeeded (document_id=$DOC_ID job_id=${DOC_JOB_ID:-none})"
  if [[ "$DOC_JOB_ID" != "null" && -n "$DOC_JOB_ID" ]]; then
    wait_for "curl -sS -H 'Authorization: Bearer $TOKEN' $BASE_URL/api/v1/jobs/$DOC_JOB_ID | jq -r '.status' | grep -q completed" 180 "document ingestion completion"
  fi
  DOC_FIXTURE_CREATED=true
}

create_reminder_minutes() {
  local minutes="$1"
  local title="$2"
  local due_utc due_local payload response reminder_id
  due_utc=$(date -u -d "+$minutes minutes" '+%Y-%m-%dT%H:%M:00Z')
  due_local=$(date -d "+$minutes minutes" '+%H:%M:00')
  payload=$(jq -n --arg title "$title" --arg due "$due_utc" --arg local "$due_local" '{title:$title, body:"Auto reminder", due_at_utc:$due, due_at_local:$local, timezone:"UTC"}')
  response=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  reminder_id=$(echo "$response" | jq -r '.data.id')
  echo "$reminder_id"
}

wait_for_notification_delivery() {
  local reminder_id="$1"
  local timeout="$2"
  wait_for "psql_query \"SELECT status FROM notification_delivery WHERE reminder_id = '$reminder_id' ORDER BY created_at DESC LIMIT 1;\" | grep -q '.'" "$timeout" "notification delivery for $reminder_id"
}

# Cleanup
cleanup_test_data() {
  log "Cleaning up test data..."
  psql_query "DELETE FROM notification_delivery WHERE created_at > NOW() - INTERVAL '1 day';" >/dev/null || true
  psql_query "DELETE FROM notes WHERE title LIKE 'MVP Test%' OR title LIKE 'Simple Slug Title %';" >/dev/null || true
  psql_query "DELETE FROM reminders WHERE title LIKE 'MVP Test Reminder%' OR title LIKE 'Recurring %' OR title LIKE 'Stage%' OR title LIKE 'Smart %' OR title LIKE 'TZ Reminder%' OR title LIKE 'Chat Reminder%' OR title LIKE 'Metric Dedup%';" >/dev/null || true
  psql_query "DELETE FROM devices WHERE push_token = 'testauth:testkey';" >/dev/null || true
  psql_query "DELETE FROM documents WHERE filename LIKE 'test-%' OR filename LIKE 'mvp-%';" >/dev/null || true
  rm -rf "$TEST_DIR"/tmp-* || true
  rm -f "$TEST_DIR"/concurrent-* "$TEST_DIR"/*.status "$TEST_DIR"/workflow-rag.json "$TEST_DIR"/rag-response.json "$TEST_DIR"/chat-*.json "$TEST_DIR"/test.exe "$TEST_DIR"/corrupted.pdf "$TEST_DIR"/$DOC_LARGE_FILENAME "$TEST_DIR"/twenty-page.pdf "$TEST_DIR"/backup-run.log "$TEST_DIR"/restore-run.log >/dev/null 2>&1 || true
  success "Cleanup complete"
}

setup() {
  section "SETUP"
  load_env_file
  load_config_json
  ensure_prereqs
  if [[ -z "$TOKEN" ]]; then
    error "API token not configured. Set API_TOKEN or provide via test-config.json"
    exit 1
  fi
  log "Using base URL: $BASE_URL"
  wait_for "curl -sS $HEALTH_URL >/dev/null" "$HEALTH_TIMEOUT" "orchestrator health endpoint"
  local status
  status=$(curl -sS "$HEALTH_URL" | jq -r '.status' || echo "")
  assert_equals "$status" "healthy" "Health endpoint reports healthy" || true
}
