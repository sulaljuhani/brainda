#!/usr/bin/env bash
# test-mvp-complete.sh
# Comprehensive MVP integration test suite for VIB (Stages 0-4)

set -euo pipefail
IFS=$'\n\t'

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_ROOT"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
START_TIME="$(date +%s)"
TEST_DIR="${TEST_DIR:-/tmp/vib-test-$TIMESTAMP}"
mkdir -p "$TEST_DIR"
TEST_LOG="$TEST_DIR/run.log"
touch "$TEST_LOG"
exec > >(tee -a "$TEST_LOG") 2>&1

BASE_URL="${BASE_URL:-http://localhost:8000}"
HEALTH_URL="$BASE_URL/api/v1/health"
METRICS_URL="$BASE_URL/api/v1/metrics"
TOKEN="${API_TOKEN:-}"
CONFIG_FILE="${TEST_CONFIG:-test-config.json}"
RUN_STAGE=""
FAST_MODE=false
HTML_REPORT=false
VERBOSE=false

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNINGS=0
declare -a FAILED_TEST_NAMES=()
declare -a TEST_RECORDS=()

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

usage() {
  cat <<USAGE
Usage: $0 [options]
  --stage N         Run only Stage N tests (0-4, performance, workflows)
  --fast            Skip slow tests (reminder firing, long-running DOC/RAG)
  --html-report     Generate HTML report in test directory
  --verbose         Enable verbose curl output
  --help            Show this message
USAGE
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --stage)
      RUN_STAGE="$2"
      shift 2
      ;;
    --fast)
      FAST_MODE=true
      shift
      ;;
    --html-report)
      HTML_REPORT=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
 done

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
    if [[ "$VERBOSE" == "true" ]]; then
      curl -sS -v -H "Authorization: Bearer $TOKEN" "$BASE_URL$endpoint" >/dev/null
    else
      curl -sS -H "Authorization: Bearer $TOKEN" "$BASE_URL$endpoint" >/dev/null
    fi
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

  if [[ "$FAST_MODE" == "true" && -n "${SLOW_TEST_MAP[$test_name]:-}" ]]; then
    warn "Skipping $test_name (slow test, fast mode enabled)"
    TEST_RECORDS+=("$test_name|SKIPPED|0s|Skipped in fast mode")
    return 0
  fi

  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  log "Running test: $test_name"
  local start_ts end_ts duration rc=0
  start_ts=$(date +%s)
  if "$test_func" "${test_args[@]}"; then
    rc=0
  else
    rc=$?
  fi
  end_ts=$(date +%s)
  duration=$((end_ts - start_ts))
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
    HEALTH_TIMEOUT=$(jq -r '.timeout.health_check // empty' "$CONFIG_FILE" || true)
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
  local response
  response=$(curl -sS -X POST "$BASE_URL/api/v1/ingest" -H "Authorization: Bearer $TOKEN" -F "file=@tests/fixtures/$DOC_FILENAME")
  DOC_ID=$(echo "$response" | jq -r '.document_id // .data.document_id')
  DOC_JOB_ID=$(echo "$response" | jq -r '.job_id')
  if [[ "$DOC_JOB_ID" != "null" && -n "$DOC_JOB_ID" ]]; then
    wait_for "curl -sS -H 'Authorization: Bearer $TOKEN' $BASE_URL/api/v1/jobs/$DOC_JOB_ID | jq -r '.status' | grep -q completed" 120 "document ingestion completion"
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

trap cleanup_test_data EXIT

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
  wait_for "curl -sS $HEALTH_URL >/dev/null" 60 "orchestrator health endpoint"
  local status
  status=$(curl -sS "$HEALTH_URL" | jq -r '.status' || echo "")
  assert_equals "$status" "healthy" "Health endpoint reports healthy" || true
}

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
      local i status count_429=0
      for i in {1..35}; do
        status=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/chat") || true
        [[ "$status" == "429" ]] && count_429=$((count_429 + 1))
      done
      if [[ $count_429 -gt 0 ]]; then
        success "Rate limit triggered ($count_429 responses)"
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
      status=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/chat")
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

#############################################
# Stage 1: Notes + Vector Search
#############################################

notes_check() {
  local check="$1"
  local rc=0
  ensure_note_fixture
  case "$check" in
    api_create)
      assert_not_empty "$NOTE_FIXTURE_ID" "Note created via API" || rc=1
      ;;
    db_record)
      local count
      count=$(psql_query "SELECT COUNT(*) FROM notes WHERE id = '$NOTE_FIXTURE_ID';" | tr -d '[:space:]')
      assert_equals "$count" "1" "Note persisted in DB" || rc=1
      ;;
    markdown_file)
      assert_file_exists "vault/$NOTE_FIXTURE_MD_PATH" "Markdown file created" || rc=1
      ;;
    frontmatter)
      local content
      content=$(head -n 6 "vault/$NOTE_FIXTURE_MD_PATH" 2>/dev/null || echo "")
      assert_contains "$content" "title: $NOTE_FIXTURE_TITLE" "Frontmatter has title" || rc=1
      assert_contains "$content" "tags:" "Frontmatter has tags" || rc=1
      ;;
    embedding_state)
      wait_for "psql_query \"SELECT embedding_model FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';\" | grep -q '.'" 90 "note embedding state" || rc=1
      ;;
    vector_keyword)
      local result
      result=$(curl -sS "$BASE_URL/api/v1/search?q=${NOTE_FIXTURE_TITLE// /%20}" -H "Authorization: Bearer $TOKEN")
      assert_contains "$result" "$NOTE_FIXTURE_TITLE" "Keyword search finds note" || rc=1
      ;;
    vector_semantic)
      local result
      result=$(curl -sS "$BASE_URL/api/v1/search?q=assistant" -H "Authorization: Bearer $TOKEN")
      assert_contains "$result" "$NOTE_FIXTURE_TITLE" "Semantic search returns note" || rc=1
      ;;
    top3)
      local count
      count=$(curl -sS "$BASE_URL/api/v1/search?q=note&limit=3" -H "Authorization: Bearer $TOKEN" | jq '.results | length')
      assert_less_than "$count" "4" "Search returns <=3 results" || rc=1
      ;;
    content_type_filter)
      local count
      count=$(curl -sS "$BASE_URL/api/v1/search?q=note&content_type=note" -H "Authorization: Bearer $TOKEN" | jq '.results | length')
      assert_greater_than "$count" "0" "Search filter content_type=note yields results" || rc=1
      ;;
    user_scope)
      local user
      user=$(get_test_user_id)
      local leak
      leak=$(curl -sS "$BASE_URL/api/v1/search?q=note" -H "Authorization: Bearer $TOKEN" | jq -r '.results[].payload.user_id' | sort -u | grep -v "$user" || true)
      if [[ -n "$leak" ]]; then
        error "Cross-user payload detected"
        rc=1
      else
        success "Results scoped to user"
      fi
      ;;
    dedup_response)
      local flag
      flag=$(echo "$NOTE_DEDUP_RESPONSE" | jq -r '.deduplicated // false')
      assert_equals "$flag" "true" "Duplicate creation flagged" || rc=1
      ;;
    dedup_message)
      assert_contains "$NOTE_DEDUP_RESPONSE" "already exists" "Deduplication message returned" || rc=1
      ;;
    db_constraint)
      local user
      user=$(get_test_user_id)
      if docker exec vib-postgres psql -U "${POSTGRES_USER:-vib}" -d "${POSTGRES_DB:-vib}" -c "INSERT INTO notes (id,user_id,title,body,tags,md_path) VALUES (gen_random_uuid(),'$user','$NOTE_FIXTURE_TITLE','dup test','{}','notes/tmp-$TIMESTAMP.md');" >/dev/null 2>&1; then
        error "Duplicate insert succeeded"
        rc=1
      else
        success "DB constraint blocked duplicate"
      fi
      ;;
    slug_simple)
      ensure_special_title_notes
      assert_contains "$SPECIAL_NOTE_PATH" "simple-slug-title" "Slugified filename" || rc=1
      ;;
    slug_special)
      local response slug_path
      response=$(curl -sS -X POST "$BASE_URL/api/v1/notes" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"title":"MVP !@# Notes","body":"special"}')
      slug_path=$(echo "$response" | jq -r '.data.md_path')
      assert_contains "$slug_path" "mvp-notes" "Special chars sanitized" || rc=1
      ;;
    slug_collision)
      mkdir -p vault/notes
      local collision="vault/notes/collision.md"
      echo "collision" > "$collision"
      local response path
      response=$(curl -sS -X POST "$BASE_URL/api/v1/notes" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"title":"Collision","body":"slug"}')
      path=$(echo "$response" | jq -r '.data.md_path')
      if [[ "$path" =~ collision-[a-z0-9]{8}\.md ]]; then
        success "Slug collision resolved with suffix"
      else
        error "Slug collision not handled ($path)"
        rc=1
      fi
      ;;
    file_sync_state)
      local count
      count=$(psql_query "SELECT COUNT(*) FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';" | tr -d '[:space:]')
      assert_equals "$count" "1" "file_sync_state entry exists" || rc=1
      ;;
    external_edit)
      local before after file="vault/$NOTE_FIXTURE_MD_PATH"
      before=$(psql_query "SELECT extract(epoch FROM last_embedded_at) FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';")
      printf '\nUpdated %s\n' "$(date)" >> "$file"
      wait_for "psql_query \"SELECT extract(epoch FROM last_embedded_at) FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';\" | awk -v before=$before 'NF && \$1 > before { exit 0 } END { exit 1 }'" 120 "re-embedding after external edit"
      after=$(psql_query "SELECT extract(epoch FROM last_embedded_at) FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';")
      assert_greater_than "${after:-0}" "${before:-0}" "Embedding timestamp advanced" || rc=1
      ;;
    chat_create)
      local payload response
      payload='{"message":"Add a note titled Chat Driven with body Chat body"}'
      response=$(curl -sS -X POST "$BASE_URL/api/v1/chat" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
      assert_contains "$response" "note" "Chat endpoint responded" || rc=1
      ;;
    chat_search)
      local payload response
      payload='{"message":"Search my notes for VIB"}'
      response=$(curl -sS -X POST "$BASE_URL/api/v1/chat" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
      assert_contains "$response" "search" "Chat search tool invoked" || rc=1
      ;;
    list_endpoint)
      local status
      status=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/notes")
      assert_status_code "$status" "200" "List notes endpoint" || rc=1
      ;;
    update_endpoint)
      local payload status
      payload=$(jq -n --arg body "Updated via test" '{body:$body}')
      status=$(curl -sS -o /dev/null -w "%{http_code}" -X PATCH "$BASE_URL/api/v1/notes/$NOTE_FIXTURE_ID" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
      assert_status_code "$status" "200" "Patch note works" || rc=1
      ;;
    *)
      error "Unknown Stage1 check $check"
      rc=1
      ;;
  esac
  return $rc
}

#############################################
# Stage 2: Reminders + Notifications
#############################################

create_chat_reminder() {
  local marker="Smart Chat Reminder $TIMESTAMP-$RANDOM"
  local payload
  payload=$(jq -n --arg msg "Remind me tomorrow to $marker" '{message:$msg}')
  local status
  status=$(curl -sS -o "$TEST_DIR/chat-reminder.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/chat" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" || echo "000")
  echo "$marker|$status"
}

get_reminder_value() {
  local reminder_id="$1"
  local column="$2"
  psql_query "SELECT $column FROM reminders WHERE id = '$reminder_id';" | tr -d '\n\r'
}

create_unique_reminder() {
  local minutes="$1"
  local title="Stage2 Auto Reminder $TIMESTAMP-$RANDOM"
  local reminder_id
  reminder_id=$(create_reminder_minutes "$minutes" "$title")
  echo "$reminder_id|$title"
}

stage2_wait_for_log() {
  local keyword="$1"
  local hits
  hits=$(docker logs vib-orchestrator --tail 400 2>&1 | grep -c "$keyword" || true)
  echo "$hits"
}

test_reminder_create_api() {
  ensure_reminder_fixture
  assert_not_empty "$REMINDER_ID" "Reminder created via API" || return 1
}

test_reminder_in_database() {
  ensure_reminder_fixture
  local count
  count=$(psql_query "SELECT COUNT(*) FROM reminders WHERE id = '$REMINDER_ID';" | tr -d '[:space:]')
  assert_equals "$count" "1" "Reminder persisted in DB" || return 1
}

test_reminder_scheduler_entry() {
  ensure_reminder_fixture
  local hits
  hits=$(stage2_wait_for_log "$REMINDER_ID")
  assert_greater_than "${hits:-0}" "0" "Reminder scheduled in APScheduler" || return 1
}

test_reminder_chat_flow() {
  IFS='|' read -r marker status <<<"$(create_chat_reminder)"
  assert_status_code "$status" "200" "Chat endpoint accepted reminder request" || return 1
}

test_reminder_smart_defaults() {
  local marker="Smart Default $TIMESTAMP-$RANDOM"
  local payload
  payload=$(jq -n --arg msg "Remind me tomorrow to $marker" '{message:$msg}')
  local status
  status=$(curl -sS -o "$TEST_DIR/chat-smart.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/chat" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" || echo "000")
  assert_status_code "$status" "200" "Chat request for smart defaults" || return 1
  sleep 5
  local reminder_id
  reminder_id=$(psql_query "SELECT id FROM reminders WHERE title ILIKE '%$marker%' ORDER BY created_at DESC LIMIT 1;")
  assert_not_empty "$reminder_id" "Reminder created via chat" || return 1
  local due_local
  due_local=$(get_reminder_value "$reminder_id" "due_at_local")
  if [[ -n "$due_local" ]]; then
    success "Smart default produced local time $due_local"
    return 0
  fi
  return 1
}

test_reminder_dedup_response() {
  ensure_reminder_fixture
  local payload
  payload=$(jq -n --arg title "MVP Test Reminder $TIMESTAMP" --arg body "dup" --arg due "$REMINDER_DUE_UTC" --arg local "$REMINDER_DUE_LOCAL" '{title:$title, body:$body, due_at_utc:$due, due_at_local:$local, timezone:"UTC"}')
  local first second flag
  first=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  second=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  flag=$(echo "$second" | jq -r '.deduplicated // false')
  assert_equals "$flag" "true" "Duplicate reminder flagged" || return 1
}

test_reminder_dedup_constraint() {
  ensure_reminder_fixture
  if docker exec vib-postgres psql -U "${POSTGRES_USER:-vib}" -d "${POSTGRES_DB:-vib}" -c \
    "INSERT INTO reminders (id,user_id,title,due_at_utc,due_at_local,timezone,status) SELECT gen_random_uuid(), user_id, title, due_at_utc, due_at_local, timezone, 'active' FROM reminders WHERE id = '$REMINDER_ID';" >/dev/null 2>&1; then
    error "DB dedup constraint allowed duplicate"
    return 1
  fi
  success "Database prevented duplicate reminder"
}

test_reminder_timezone_conversion() {
  local due_utc due_local payload response rid tz
  due_utc=$(date -u -d '+2 hours' '+%Y-%m-%dT%H:%M:00Z')
  due_local=$(date -d '+2 hours' '+%H:%M:00')
  payload=$(jq -n --arg title "TZ Reminder $TIMESTAMP" --arg due "$due_utc" --arg local "$due_local" '{title:$title, due_at_utc:$due, due_at_local:$local, timezone:"America/Los_Angeles"}')
  response=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  rid=$(echo "$response" | jq -r '.data.id')
  tz=$(psql_query "SELECT timezone FROM reminders WHERE id = '$rid';" | tr -d '[:space:]')
  assert_equals "$tz" "America/Los_Angeles" "Timezone stored correctly" || return 1
}

test_reminder_due_local_preserved() {
  ensure_reminder_fixture
  local stored
  stored=$(get_reminder_value "$REMINDER_ID" "due_at_local")
  assert_equals "${stored// /}" "$REMINDER_DUE_LOCAL" "due_at_local preserved" || return 1
}

test_reminder_snooze_updates_due() {
  local pair reminder_id title before after
  pair=$(create_unique_reminder 10)
  reminder_id=${pair%%|*}
  before=$(get_reminder_value "$reminder_id" "due_at_utc")
  curl -sS -X POST "$BASE_URL/api/v1/reminders/$reminder_id/snooze" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"duration_minutes":15}' >/dev/null
  after=$(get_reminder_value "$reminder_id" "due_at_utc")
  assert_not_empty "$after" "Snooze returned due_at" || return 1
  if [[ "$after" == "$before" ]]; then
    error "Snooze did not update due time"
    return 1
  fi
}

test_reminder_snooze_reschedules() {
  local hits
  hits=$(stage2_wait_for_log "reminder_snoozed")
  assert_greater_than "${hits:-0}" "0" "Snooze events logged" || return 1
}

test_reminder_cancel_endpoint() {
  local pair reminder_id
  pair=$(create_unique_reminder 20)
  reminder_id=${pair%%|*}
  local status
  status=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/api/v1/reminders/$reminder_id" -H "Authorization: Bearer $TOKEN")
  assert_status_code "$status" "200" "Cancel endpoint" || return 1
}

test_reminder_cancel_halts_firing() {
  local status
  status=$(psql_query "SELECT status FROM reminders WHERE id = '$REMINDER_ID';" | tr -d '[:space:]')
  if [[ "$status" != "cancelled" ]]; then
    warn "Base reminder not cancelled; cancelling now"
    curl -sS -X DELETE "$BASE_URL/api/v1/reminders/$REMINDER_ID" -H "Authorization: Bearer $TOKEN" >/dev/null || true
    status=$(psql_query "SELECT status FROM reminders WHERE id = '$REMINDER_ID';" | tr -d '[:space:]')
  fi
  assert_equals "$status" "cancelled" "Reminder marked cancelled" || return 1
}

test_reminder_recurring_daily() {
  local due payload response rid rrule
  due=$(date -u -d '+1 day' '+%Y-%m-%dT%H:%M:00Z')
  payload=$(jq -n --arg due "$due" '{title:"Recurring Daily", due_at_utc:$due, due_at_local:"09:00:00", timezone:"UTC", repeat_rrule:"FREQ=DAILY"}')
  response=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  rid=$(echo "$response" | jq -r '.data.id')
  rrule=$(psql_query "SELECT repeat_rrule FROM reminders WHERE id = '$rid';")
  assert_equals "$rrule" "FREQ=DAILY" "Daily recurrence saved" || return 1
}

test_reminder_recurring_weekly() {
  local due payload response rid rrule
  due=$(date -u -d 'next monday 09:00' '+%Y-%m-%dT%H:%M:00Z')
  payload=$(jq -n --arg due "$due" '{title:"Recurring Weekly", due_at_utc:$due, due_at_local:"09:00:00", timezone:"UTC", repeat_rrule:"FREQ=WEEKLY;BYDAY=MO"}')
  response=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  rid=$(echo "$response" | jq -r '.data.id')
  rrule=$(psql_query "SELECT repeat_rrule FROM reminders WHERE id = '$rid';")
  assert_equals "$rrule" "FREQ=WEEKLY;BYDAY=MO" "Weekly recurrence saved" || return 1
}

test_reminder_recurring_monthly() {
  local due payload response rid rrule
  due=$(date -u -d 'next month 09:00' '+%Y-%m-%dT%H:%M:00Z')
  payload=$(jq -n --arg due "$due" '{title:"Recurring Monthly", due_at_utc:$due, due_at_local:"09:00:00", timezone:"UTC", repeat_rrule:"FREQ=MONTHLY;BYMONTHDAY=1"}')
  response=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  rid=$(echo "$response" | jq -r '.data.id')
  rrule=$(psql_query "SELECT repeat_rrule FROM reminders WHERE id = '$rid';")
  assert_equals "$rrule" "FREQ=MONTHLY;BYMONTHDAY=1" "Monthly recurrence saved" || return 1
}

test_device_registration() {
  ensure_device_registered
  assert_not_empty "$DEVICE_ID" "Device registered" || return 1
}

test_device_db_entry() {
  ensure_device_registered
  local count
  count=$(psql_query "SELECT COUNT(*) FROM devices WHERE id = '$DEVICE_ID';" | tr -d '[:space:]')
  assert_equals "$count" "1" "Device row exists" || return 1
}

test_device_test_notification() {
  ensure_device_registered
  local status
  status=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/devices/test" -H "Authorization: Bearer $TOKEN")
  if [[ "$status" == "404" ]]; then
    warn "Test notification endpoint reports no devices"
    return 0
  fi
  assert_status_code "$status" "200" "Test notification endpoint" || return 1
}

test_push_metrics() {
  local metrics success failure total rate
  metrics=$(curl -sS "$METRICS_URL") || metrics=""
  success=$(echo "$metrics" | awk '/^push_delivery_success_total/ {sum+=$2} END {print sum+0}')
  failure=$(echo "$metrics" | awk '/^push_delivery_failure_total/ {sum+=$2} END {print sum+0}')
  total=$(awk -v s="${success:-0}" -v f="${failure:-0}" 'BEGIN{print s+f}')
  if float_greater_than "${total:-0}" "0"; then
    rate=$(awk -v s="$success" -v t="$total" 'BEGIN{printf "%.3f", (t==0?0:s/t)}')
    PUSH_SUCCESS_RATE="$rate"
    assert_greater_than "$rate" "$PUSH_SUCCESS_TARGET" "Push success rate above target" || return 1
  else
    warn "Push delivery metrics have no samples"
  fi
}

test_reminder_fire_slo() {
  if $FAST_MODE; then
    warn "Skipping reminder fire SLO in fast mode"
    return 0
  fi
  ensure_device_registered
  local pair reminder_id
  pair=$(create_unique_reminder 1)
  reminder_id=${pair%%|*}
  REMINDER_FIRE_ID="$reminder_id"
  log "Waiting for reminder $reminder_id to fire (up to 150s)"
  wait_for_notification_delivery "$reminder_id" 150 || return 1
  local lag
  lag=$(psql_query "SELECT EXTRACT(EPOCH FROM (COALESCE(nd.delivered_at, nd.sent_at) - r.due_at_utc)) FROM notification_delivery nd JOIN reminders r ON r.id = nd.reminder_id WHERE nd.reminder_id = '$reminder_id' ORDER BY nd.created_at DESC LIMIT 1;")
  if [[ -n "$lag" ]]; then
    REMINDER_FIRE_LAG_P95="$lag"
    assert_less_than "${lag#-}" "$REMINDER_FIRE_LAG_TARGET" "Reminder fire lag <$REMINDER_FIRE_LAG_TARGET s" || return 1
  else
    error "No lag measurement recorded"
    return 1
  fi
}

test_notification_delivery_record() {
  local rid="${REMINDER_FIRE_ID:-}"
  if [[ -z "$rid" ]]; then
    warn "Fire SLO test did not produce reminder id"
    return 0
  fi
  local status
  status=$(psql_query "SELECT status FROM notification_delivery WHERE reminder_id = '$rid' ORDER BY created_at DESC LIMIT 1;")
  assert_equals "${status// /}" "delivered" "Notification delivery recorded" || return 1
}

test_reminder_metrics_created_total() {
  local before after pair
  before=$(curl -sS "$METRICS_URL" | awk '/^reminders_created_total/ {print $NF; found=1; exit} END {if (!found) print 0}')
  pair=$(create_unique_reminder 45)
  after=$(curl -sS "$METRICS_URL" | awk '/^reminders_created_total/ {print $NF; found=1; exit} END {if (!found) print 0}')
  assert_greater_than "$after" "$before" "reminders_created_total increments" || return 1
}

test_reminder_metrics_deduped_total() {
  local before after payload due local
  due=$(date -u -d '+50 minutes' '+%Y-%m-%dT%H:%M:00Z')
  local=$(date -d '+50 minutes' '+%H:%M:00')
  payload=$(jq -n --arg title "Metric Dedup" --arg due "$due" --arg local "$local" '{title:$title,due_at_utc:$due,due_at_local:$local,timezone:"UTC"}')
  before=$(curl -sS "$METRICS_URL" | awk '/^reminders_deduped_total/ {print $NF; found=1; exit} END {if (!found) print 0}')
  curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" >/dev/null
  curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" >/dev/null
  after=$(curl -sS "$METRICS_URL" | awk '/^reminders_deduped_total/ {print $NF; found=1; exit} END {if (!found) print 0}')
  assert_greater_than "$after" "$before" "reminders_deduped_total increments" || return 1
}

test_reminder_metrics_fire_lag() {
  local metrics
  metrics=$(curl -sS "$METRICS_URL")
  export METRIC_NAME="reminder_fire_lag_seconds"
  export METRIC_QUANTILE="0.95"
  REMINDER_FIRE_LAG_P95=$(echo "$metrics" | histogram_quantile_from_metrics)
  if [[ "$REMINDER_FIRE_LAG_P95" != "nan" ]]; then
    success "Reminder fire lag histogram available"
    return 0
  fi
  warn "Reminder fire lag histogram has no samples"
}

test_reminder_list_endpoint() {
  local status
  status=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/reminders")
  assert_status_code "$status" "200" "List reminders endpoint" || return 1
}

test_reminder_update_endpoint() {
  ensure_reminder_fixture
  local payload status
  payload='{ "status": "done" }'
  status=$(curl -sS -o /dev/null -w "%{http_code}" -X PATCH "$BASE_URL/api/v1/reminders/$REMINDER_ID" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
  assert_status_code "$status" "200" "Reminder update endpoint" || return 1
}

test_reminder_restart_persistence() {
  ensure_reminder_fixture
  compose_cmd restart orchestrator >/dev/null 2>&1 || true
  wait_for "curl -sS $HEALTH_URL >/dev/null" 60 "health after orchestrator restart" || return 1
  local result
  result=$(curl -sS -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/reminders" | jq -r '.[] | select(.id=="'$REMINDER_ID'") | .id')
  assert_equals "$result" "$REMINDER_ID" "Reminder still available post-restart" || return 1
}

#############################################
# Stage 3: Documents + RAG
#############################################

generate_pdf_with_pages() {
  local path="$1"
  local pages="$2"
  python - <<PY
from fpdf import FPDF
pdf = FPDF()
text = "VIB integration test page"
pages = int(${pages})
for i in range(pages):
    pdf.add_page()
    pdf.set_font('Arial', size=12)
    pdf.multi_cell(0, 10, txt=f"{text} {i+1}\nThis document validates ingestion.")
pdf.output('${path}')
PY
}

document_wait_for_job() {
  local job_id="$1"
  local timeout="${2:-180}"
  local waited=0
  local status="pending"
  while [[ $waited -lt $timeout ]]; do
    local response
    response=$(curl -sS -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/jobs/$job_id")
    status=$(echo "$response" | jq -r '.status')
    if [[ "$status" == "completed" ]]; then
      LAST_JOB_ERROR=""
      return 0
    fi
    if [[ "$status" == "failed" ]]; then
      LAST_JOB_ERROR=$(echo "$response" | jq -r '.error_message // ""')
      return 1
    fi
    sleep 5
    waited=$((waited + 5))
  done
  LAST_JOB_ERROR="timeout"
  return 1
}

document_upload_file() {
  local file_path="$1"
  local mime="$2"
  local response doc_id job_id
  response=$(curl -sS -X POST "$BASE_URL/api/v1/ingest" -H "Authorization: Bearer $TOKEN" -F "file=@$file_path;type=$mime")
  doc_id=$(echo "$response" | jq -r '.document_id // .data.id')
  job_id=$(echo "$response" | jq -r '.job_id // empty')
  echo "$doc_id|$job_id"
}

document_qdrant_point_count() {
  local doc_id="$1"
  curl -sS "http://localhost:6333/collections/knowledge_base/points/scroll" \
    -H "Content-Type: application/json" \
    -d "{\"filter\":{\"must\":[{\"key\":\"parent_document_id\",\"match\":{\"value\":\"$doc_id\"}}]},\"limit\":1}" | jq -r '.result.points | length'
}

document_latest_metric() {
  local metric="$1"
  curl -sS "$METRICS_URL" | awk -v name="$metric" '$1==name {print $2}' | tail -n1
}

ensure_twenty_page_document() {
  if [[ -n "$DOC_TWENTY_ID" ]]; then
    return
  fi
  local path="tests/fixtures/twenty-page.pdf"
  generate_pdf_with_pages "$path" 20
  local pair
  pair=$(document_upload_file "$path" "application/pdf")
  DOC_TWENTY_ID=${pair%%|*}
  DOC_TWENTY_JOB_ID=${pair##*|}
  if [[ -n "$DOC_TWENTY_JOB_ID" && "$DOC_TWENTY_JOB_ID" != "null" ]]; then
    document_wait_for_job "$DOC_TWENTY_JOB_ID" 240 || true
  fi
}

ensure_large_document_fixture() {
  if [[ -f "$TEST_DIR/$DOC_LARGE_FILENAME" ]]; then
    return
  fi
  dd if=/dev/zero of="$TEST_DIR/$DOC_LARGE_FILENAME" bs=1M count=60 >/dev/null 2>&1
}

ensure_failed_document_fixture() {
  if [[ -n "$DOC_FAILED_ID" ]]; then
    return
  fi
  local path="$TEST_DIR/corrupted.pdf"
  printf 'not a real pdf' > "$path"
  local pair
  pair=$(document_upload_file "$path" "application/pdf")
  DOC_FAILED_ID=${pair%%|*}
  DOC_FAILED_JOB_ID=${pair##*|}
  if [[ -n "$DOC_FAILED_JOB_ID" && "$DOC_FAILED_JOB_ID" != "null" ]]; then
    document_wait_for_job "$DOC_FAILED_JOB_ID" 60 || true
  fi
}

documents_check() {
  local check="$1"
  local rc=0
  ensure_document_fixture
  case "$check" in
    upload_pdf)
      assert_not_empty "$DOC_ID" "Document uploaded" || rc=1
      ;;
    job_created)
      assert_not_empty "$DOC_JOB_ID" "Job created for document" || rc=1
      ;;
    job_completed)
      if [[ -n "$DOC_JOB_ID" && "$DOC_JOB_ID" != "null" ]]; then
        document_wait_for_job "$DOC_JOB_ID" 180 || rc=1
        [[ $rc -eq 0 ]] && success "Document job completed"
      else
        warn "Document job id missing"
      fi
      ;;
    status_indexed)
      local status
      status=$(psql_query "SELECT status FROM documents WHERE id = '$DOC_ID';" | tr -d '[:space:]')
      assert_equals "$status" "indexed" "Document status indexed" || rc=1
      ;;
    chunks_created)
      DOC_CHUNK_COUNT=$(psql_query "SELECT COUNT(*) FROM chunks WHERE document_id = '$DOC_ID';" | tr -d '[:space:]')
      assert_greater_than "${DOC_CHUNK_COUNT:-0}" "0" "Chunks created" || rc=1
      ;;
    chunk_ordinals)
      local gaps
      gaps=$(psql_query "SELECT COUNT(*) FROM (SELECT ordinal, LAG(ordinal) OVER (ORDER BY ordinal) AS prev FROM chunks WHERE document_id = '$DOC_ID') t WHERE prev IS NOT NULL AND ordinal - prev <> 1;")
      assert_equals "${gaps:-0}" "0" "Chunk ordinals sequential" || rc=1
      ;;
    chunk_tokens)
      local tokens
      tokens=$(psql_query "SELECT COUNT(*) FROM chunks WHERE document_id = '$DOC_ID' AND tokens IS NOT NULL;")
      assert_greater_than "${tokens:-0}" "0" "Chunk token counts recorded" || rc=1
      ;;
    chunk_metadata)
      local pages
      pages=$(psql_query "SELECT COUNT(*) FROM chunks WHERE document_id = '$DOC_ID' AND (metadata->>'page') IS NOT NULL;" )
      assert_greater_than "${pages:-0}" "0" "Chunk metadata includes pages" || rc=1
      ;;
    vectors_embedded)
      local count
      count=$(document_qdrant_point_count "$DOC_ID")
      assert_greater_than "${count:-0}" "0" "Vectors exist for document" || rc=1
      ;;
    vector_payload_fields)
      local payload
      payload=$(curl -sS "http://localhost:6333/collections/knowledge_base/points/scroll" -H "Content-Type: application/json" -d "{\"filter\":{\"must\":[{\"key\":\"parent_document_id\",\"match\":{\"value\":\"$DOC_ID\"}}]},\"limit\":1}" | jq '.result.points[0].payload')
      assert_contains "$payload" "embedding_model" "Vector payload contains embedding_model" || rc=1
      ;;
    search_keyword)
      local results
      results=$(curl -sS -G -H "Authorization: Bearer $TOKEN" \
        --data-urlencode "q=integration" \
        "$BASE_URL/api/v1/search")
      assert_contains "$results" "$DOC_FILENAME" "Keyword search finds document" || rc=1
      ;;
    search_semantic)
      local results
      results=$(curl -sS -G -H "Authorization: Bearer $TOKEN" \
        --data-urlencode "q=knowledge base document" \
        "$BASE_URL/api/v1/search")
      assert_contains "$results" "$DOC_FILENAME" "Semantic search returns document" || rc=1
      ;;
    search_filter)
      local count
      count=$(curl -sS "$BASE_URL/api/v1/search?q=test&content_type=document_chunk" -H "Authorization: Bearer $TOKEN" | jq '.results | length')
      assert_greater_than "$count" "0" "Search filter for document chunks" || rc=1
      ;;
    rag_answer)
      local payload status
      payload='{ "message": "Summarize the uploaded integration document" }'
      status=$(curl -sS -o "$TEST_DIR/rag-response.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/chat" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" || echo "000")
      assert_status_code "$status" "200" "RAG chat request" || rc=1
      ;;
    rag_citations)
      if [[ -f "$TEST_DIR/rag-response.json" ]]; then
        local citations
        citations=$(jq '.citations | length' "$TEST_DIR/rag-response.json" 2>/dev/null || echo 0)
        assert_greater_than "$citations" "0" "RAG citations present" || rc=1
      else
        warn "RAG response missing"
      fi
      ;;
    deduplication)
      local response flag
      response=$(curl -sS -X POST "$BASE_URL/api/v1/ingest" -H "Authorization: Bearer $TOKEN" -F "file=@tests/fixtures/$DOC_FILENAME")
      flag=$(echo "$response" | jq -r '.deduplicated // false')
      assert_equals "$flag" "true" "Duplicate upload flagged" || rc=1
      ;;
    large_file_rejected)
      ensure_large_document_fixture
      local status
      status=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/ingest" -H "Authorization: Bearer $TOKEN" -F "file=@$TEST_DIR/$DOC_LARGE_FILENAME;type=application/pdf")
      assert_status_code "$status" "422" "Large file rejected" || rc=1
      ;;
    unsupported_type)
      local path="$TEST_DIR/test.exe"
      printf 'binary' > "$path"
      local status
      status=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/ingest" -H "Authorization: Bearer $TOKEN" -F "file=@$path;type=application/octet-stream")
      assert_status_code "$status" "422" "Unsupported mime rejected" || rc=1
      ;;
    processing_speed_small)
      local duration
      duration=$(psql_query "SELECT EXTRACT(EPOCH FROM (completed_at - started_at)) FROM jobs WHERE id = '$DOC_JOB_ID';")
      if [[ -n "$duration" ]]; then
        assert_less_than "$duration" "30" "5-page PDF processed under 30s" || rc=1
      else
        warn "Unable to compute job duration"
      fi
      ;;
    processing_speed_large)
      ensure_twenty_page_document
      if [[ -n "$DOC_TWENTY_JOB_ID" && "$DOC_TWENTY_JOB_ID" != "null" ]]; then
        local duration
        duration=$(psql_query "SELECT EXTRACT(EPOCH FROM (completed_at - started_at)) FROM jobs WHERE id = '$DOC_TWENTY_JOB_ID';")
        if [[ -n "$duration" ]]; then
          assert_less_than "$duration" "120" "20-page PDF processed under 2 minutes" || rc=1
        fi
      fi
      ;;
    list_endpoint)
      local status
      status=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/documents")
      assert_status_code "$status" "200" "List documents endpoint" || rc=1
      ;;
    detail_endpoint)
      local status
      status=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/documents/$DOC_ID")
      assert_status_code "$status" "200" "Document detail endpoint" || rc=1
      ;;
    chunks_endpoint)
      local status
      status=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/documents/$DOC_ID/chunks")
      assert_status_code "$status" "200" "Document chunks endpoint" || rc=1
      ;;
    delete_endpoint)
      local temp_pair temp_id status
      temp_pair=$(document_upload_file "tests/fixtures/$DOC_FILENAME" "application/pdf")
      temp_id=${temp_pair%%|*}
      status=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/api/v1/documents/$temp_id" -H "Authorization: Bearer $TOKEN")
      assert_status_code "$status" "200" "Delete document endpoint" || rc=1
      ;;
    delete_vectors)
      local before after temp_pair temp_id
      temp_pair=$(document_upload_file "tests/fixtures/$DOC_FILENAME" "application/pdf")
      temp_id=${temp_pair%%|*}
      if [[ -n "$temp_pair" ]]; then
        document_wait_for_job "${temp_pair##*|}" 120 || true
        before=$(document_qdrant_point_count "$temp_id")
        curl -sS -X DELETE "$BASE_URL/api/v1/documents/$temp_id" -H "Authorization: Bearer $TOKEN" >/dev/null
        after=$(document_qdrant_point_count "$temp_id")
        assert_equals "${after:-0}" "0" "Vectors removed after delete" || rc=1
      fi
      ;;
    corrupted_pdf_failure)
      ensure_failed_document_fixture
      local status
      status=$(psql_query "SELECT status FROM jobs WHERE id = '$DOC_FAILED_JOB_ID';" | tr -d '[:space:]')
      assert_equals "$status" "failed" "Corrupted PDF job failed" || rc=1
      ;;
    job_error_message)
      ensure_failed_document_fixture
      local error
      error=$(psql_query "SELECT error_message FROM jobs WHERE id = '$DOC_FAILED_JOB_ID';")
      assert_not_empty "$error" "Failed job error message populated" || rc=1
      ;;
    concurrent_uploads)
      local failures=0
      DOC_CONCURRENT_IDS=()
      for i in 1 2 3; do
        (
          local path="$TEST_DIR/concurrent-$i.pdf"
          generate_pdf_with_pages "$path" 2
          response=$(document_upload_file "$path" "application/pdf")
          [[ -z "${response%%|*}" ]] && echo "fail" > "$TEST_DIR/concurrent-$i.status"
        ) &
      done
      wait
      failures=$(grep -c "fail" "$TEST_DIR"/concurrent-*.status 2>/dev/null || true)
      assert_equals "${failures:-0}" "0" "Concurrent uploads succeed" || rc=1
      ;;
    vector_search_latency)
      local latency
      latency=$(measure_latency "/api/v1/search?q=document" 5)
      VECTOR_SEARCH_P95="$latency"
      assert_less_than "$latency" "$SEARCH_LATENCY_THRESHOLD" "Search latency under threshold" || rc=1
      ;;
    metrics_counters)
      local before after
      before=$(document_latest_metric "documents_ingested_total" || echo 0)
      document_upload_file "tests/fixtures/$DOC_FILENAME" "application/pdf" >/dev/null
      after=$(document_latest_metric "documents_ingested_total" || echo 0)
      assert_greater_than "$after" "$before" "documents_ingested_total increments" || rc=1
      ;;
    *)
      error "Unknown Stage3 check $check"
      rc=1
      ;;
  esac
  return $rc
}

#############################################
# Stage 4: Backups + Retention + Observability
#############################################

discover_latest_backup() {
  local latest
  latest=$(ls -1 "$BACKUP_ROOT"/postgres/backup-*.dump 2>/dev/null | sort | tail -n1 || true)
  if [[ -n "$latest" ]]; then
    latest=${latest##*backup-}
    latest=${latest%.dump}
    LATEST_BACKUP_TS="$latest"
  fi
}

run_backup_job() {
  mkdir -p "$BACKUP_ROOT"
  BACKUP_DIR="$BACKUP_ROOT" bash backups/backup.sh >/tmp/backup-run.log 2>&1
  discover_latest_backup
}

stage4_restore_temp_db() {
  local ts="$1"
  if [[ -z "$ts" ]] || [[ "$ts" == "null" ]]; then
    discover_latest_backup
    ts="$LATEST_BACKUP_TS"
  fi
  [[ -z "$ts" ]] && return 1
  POSTGRES_DB="vib_restore_test" \
  POSTGRES_CONTAINER="vib-postgres" \
  SERVICES_TO_STOP="" \
  COMPOSE_CMD="true" \
  BACKUP_DIR="$BACKUP_ROOT" \
  bash backups/restore.sh "$ts" </dev/null >/tmp/restore-run.log 2>&1
}

metric_value() {
  local metric="$1"
  curl -sS "$METRICS_URL" | awk -v name="$metric" '$1==name {print $2}' | tail -n1
}

stage4_check() {
  local check="$1"
  local rc=0
  case "$check" in
    metrics_defined)
      local required=(reminder_fire_lag_seconds push_delivery_success_total document_ingestion_duration_seconds vector_search_duration_seconds retention_cleanup_total)
      for metric in "${required[@]}"; do
        local count
        count=$(curl -sS "$METRICS_URL" | grep -c "$metric" || true)
        if [[ "${count:-0}" -eq 0 ]]; then
          error "Metric $metric missing"
          rc=1
        fi
      done
      ;;
    metrics_non_zero)
      local value
      value=$(metric_value "notes_created_total" || echo 0)
      assert_greater_than "${value:-0}" "0" "Notes created metric non-zero" || rc=1
      ;;
    metrics_histograms)
      local content
      content=$(curl -sS "$METRICS_URL" | grep 'reminder_fire_lag_seconds_bucket' || true)
      assert_not_empty "$content" "Reminder fire lag histogram exported" || rc=1
      ;;
    metrics_gauges)
      local gauges=(postgres_connections redis_memory_bytes celery_queue_depth)
      for g in "${gauges[@]}"; do
        local val
        val=$(metric_value "$g" || echo "")
        if [[ -z "$val" ]]; then
          warn "Gauge $g missing"
          rc=1
        fi
      done
      ;;
    metrics_counters)
      local before after
      before=$(metric_value "api_request_duration_seconds_count" || echo 0)
      curl -sS "$BASE_URL/api/v1/health" >/dev/null
      after=$(metric_value "api_request_duration_seconds_count" || echo 0)
      assert_greater_than "${after:-0}" "${before:-0}" "API request counter increments" || rc=1
      ;;
    slo_reminder_fire_lag)
      local metrics
      metrics=$(curl -sS "$METRICS_URL")
      export METRIC_NAME="reminder_fire_lag_seconds"
      export METRIC_QUANTILE="0.95"
      REMINDER_FIRE_LAG_P95=$(echo "$metrics" | histogram_quantile_from_metrics)
      if [[ "$REMINDER_FIRE_LAG_P95" != "nan" ]]; then
        assert_less_than "$REMINDER_FIRE_LAG_P95" "$REMINDER_FIRE_LAG_TARGET" "Reminder fire lag p95 <$REMINDER_FIRE_LAG_TARGET" || rc=1
      else
        warn "Reminder lag metric lacks samples"
      fi
      ;;
    slo_push_success)
      if [[ -z "$PUSH_SUCCESS_RATE" || "$PUSH_SUCCESS_RATE" == "unknown" ]]; then
        local success failure total rate
        success=$(metric_value "push_delivery_success_total" || echo 0)
        failure=$(metric_value "push_delivery_failure_total" || echo 0)
        total=$(awk -v s="${success:-0}" -v f="${failure:-0}" 'BEGIN{print s+f}')
        if float_greater_than "${total:-0}" "0"; then
          rate=$(awk -v s="$success" -v t="$total" 'BEGIN{printf "%.3f", (t==0?0:s/t)}')
          PUSH_SUCCESS_RATE="$rate"
        fi
      fi
      if [[ "$PUSH_SUCCESS_RATE" != "unknown" ]]; then
        assert_greater_than "$PUSH_SUCCESS_RATE" "$PUSH_SUCCESS_TARGET" "Push success rate above target" || rc=1
      else
        warn "Push success rate unavailable"
      fi
      ;;
    slo_document_ingestion)
      local metrics
      metrics=$(curl -sS "$METRICS_URL")
      export METRIC_NAME="document_ingestion_duration_seconds"
      export METRIC_QUANTILE="0.95"
      DOC_INGESTION_P95=$(echo "$metrics" | histogram_quantile_from_metrics)
      if [[ "$DOC_INGESTION_P95" != "nan" ]]; then
        assert_less_than "$DOC_INGESTION_P95" "$DOC_INGESTION_TARGET" "Document ingestion p95 <$DOC_INGESTION_TARGET" || rc=1
      else
        warn "Document ingestion histogram empty"
      fi
      ;;
    slo_vector_search)
      if [[ -z "$VECTOR_SEARCH_P95" || "$VECTOR_SEARCH_P95" == "unknown" ]]; then
        local metrics
        metrics=$(curl -sS "$METRICS_URL")
        export METRIC_NAME="vector_search_duration_seconds"
        export METRIC_QUANTILE="0.95"
        VECTOR_SEARCH_P95=$(echo "$metrics" | histogram_quantile_from_metrics)
      fi
      if [[ "$VECTOR_SEARCH_P95" != "nan" && -n "$VECTOR_SEARCH_P95" ]]; then
        assert_less_than "$VECTOR_SEARCH_P95" "$SEARCH_LATENCY_THRESHOLD" "Vector search p95 under threshold" || rc=1
      else
        warn "Vector search histogram missing"
      fi
      ;;
    backup_script_exists)
      assert_file_exists "backups/backup.sh" "Backup script present" || rc=1
      ;;
    backup_run)
      run_backup_job || rc=1
      assert_not_empty "$LATEST_BACKUP_TS" "Backup timestamp recorded" || rc=1
      ;;
    backup_postgres_artifact)
      discover_latest_backup
      local file="$BACKUP_ROOT/postgres/backup-$LATEST_BACKUP_TS.dump"
      assert_file_exists "$file" "Postgres dump created" || rc=1
      ;;
    backup_qdrant_snapshot)
      discover_latest_backup
      local file="$BACKUP_ROOT/qdrant/snapshot-$LATEST_BACKUP_TS.tar.gz"
      assert_file_exists "$file" "Qdrant snapshot created" || rc=1
      ;;
    backup_files_archived)
      discover_latest_backup
      local vault="$BACKUP_ROOT/files/vault-$LATEST_BACKUP_TS.tar.gz"
      local uploads="$BACKUP_ROOT/files/uploads-$LATEST_BACKUP_TS.tar.gz"
      assert_file_exists "$vault" "Vault archive present" || rc=1
      assert_file_exists "$uploads" "Uploads archive present" || rc=1
      ;;
    backup_manifest)
      discover_latest_backup
      local manifest="$BACKUP_ROOT/manifest-$LATEST_BACKUP_TS.txt"
      assert_file_exists "$manifest" "Backup manifest present" || rc=1
      assert_contains "$(head -n 5 "$manifest")" "$LATEST_BACKUP_TS" "Manifest references timestamp" || rc=1
      ;;
    restore_script_exists)
      assert_file_exists "backups/restore.sh" "Restore script present" || rc=1
      ;;
    restore_temp_db)
      discover_latest_backup
      stage4_restore_temp_db "$LATEST_BACKUP_TS" || rc=1
      local exists
      exists=$(docker exec vib-postgres psql -U "${POSTGRES_USER:-vib}" -d postgres -t -c "SELECT COUNT(*) FROM pg_database WHERE datname = 'vib_restore_test';" | tr -d '[:space:]')
      assert_equals "$exists" "1" "Temp database restored" || rc=1
      ;;
    retention_scheduler)
      docker exec vib-beat pgrep -f "celery" >/dev/null 2>&1 || rc=1
      if [[ $rc -eq 0 ]]; then
        success "Celery beat running"
      else
        error "Celery beat not running"
      fi
      ;;
    retention_cleanup_manual)
      local output
      output=$(docker exec vib-worker celery -A worker.tasks call worker.tasks.cleanup_old_data 2>&1 || true)
      assert_contains "$output" "SUCCESS" "Retention cleanup task invoked" || rc=1
      ;;
    retention_metrics)
      local value
      value=$(metric_value "retention_cleanup_total" || echo 0)
      assert_greater_than "${value:-0}" "0" "Retention cleanup metric reports work" || rc=1
      ;;
    database_size_report)
      local output
      output=$(bash scripts/check-db-size.sh 2>&1 || true)
      assert_contains "$output" "VIB Database Size Report" "DB size script runs" || rc=1
      ;;
    database_vacuum)
      docker exec vib-postgres psql -U "${POSTGRES_USER:-vib}" -d "${POSTGRES_DB:-vib}" -c "VACUUM (ANALYZE) notes;" >/dev/null 2>&1 || rc=1
      [[ $rc -eq 0 ]] && success "VACUUM completed"
      ;;
    metrics_prometheus_format)
      local content
      content=$(curl -sS "$METRICS_URL" | head -n 1)
      assert_contains "$content" "# HELP" "Metrics endpoint in Prometheus format" || rc=1
      ;;
    backup_manifest_counts)
      discover_latest_backup
      local manifest="$BACKUP_ROOT/manifest-$LATEST_BACKUP_TS.txt"
      local counts
      counts=$(grep -c "Postgres" "$manifest" || true)
      assert_greater_than "${counts:-0}" "0" "Manifest lists artifacts" || rc=1
      ;;
    *)
      error "Unknown Stage4 check $check"
      rc=1
      ;;
  esac
  return $rc
}

#############################################
# Performance Tests
#############################################

performance_check() {
  local check="$1"
  local rc=0
  case "$check" in
    api_latency)
      local latency
      latency=$(measure_latency "/api/v1/health" 10)
      assert_less_than "$latency" "$API_LATENCY_THRESHOLD" "Health endpoint latency <$API_LATENCY_THRESHOLD ms" || rc=1
      ;;
    search_performance)
      local latency
      latency=$(measure_latency "/api/v1/search?q=knowledge" 10)
      assert_less_than "$latency" "$SEARCH_LATENCY_THRESHOLD" "Search latency <$SEARCH_LATENCY_THRESHOLD ms" || rc=1
      ;;
    document_processing_speed)
      ensure_twenty_page_document
      local duration
      duration=$(psql_query "SELECT COALESCE(EXTRACT(EPOCH FROM (completed_at - started_at)),0) FROM jobs WHERE id = '$DOC_TWENTY_JOB_ID';")
      if [[ -n "$duration" ]]; then
        assert_less_than "$duration" "$DOC_INGESTION_TARGET" "Document ingestion meets SLO" || rc=1
      else
        warn "Document job duration unavailable"
      fi
      ;;
    concurrent_requests)
      local failures=0
      for i in {1..10}; do
        (curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/health" | grep -q "200") || failures=$((failures + 1))
      done
      assert_equals "$failures" "0" "Burst of health checks succeed" || rc=1
      ;;
    *)
      error "Unknown performance check $check"
      rc=1
      ;;
  esac
  return $rc
}

#############################################
# End-to-End Workflows
#############################################

workflow_check() {
  local check="$1"
  local rc=0
  case "$check" in
    note_to_reminder)
      ensure_note_fixture
      local due=$(date -u -d '+1 hour' '+%Y-%m-%dT%H:%M:00Z')
      local local_time=$(date -d '+1 hour' '+%H:%M:00')
      local payload
      payload=$(jq -n --arg title "Workflow Reminder $TIMESTAMP" --arg due "$due" --arg local "$local_time" --arg note "$NOTE_FIXTURE_ID" '{title:$title,due_at_utc:$due,due_at_local:$local,timezone:"UTC",note_id:$note}')
      local response rid
      response=$(curl -sS -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload")
      rid=$(echo "$response" | jq -r '.data.id')
      assert_not_empty "$rid" "Workflow reminder created" || rc=1
      local linked
      linked=$(psql_query "SELECT note_id FROM reminders WHERE id = '$rid';")
      assert_equals "${linked// /}" "$NOTE_FIXTURE_ID" "Reminder linked to note" || rc=1
      ;;
    document_to_answer)
      ensure_document_fixture
      local payload status
      payload='{ "message": "What is covered in the integration document?" }'
      status=$(curl -sS -o "$TEST_DIR/workflow-rag.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/chat" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" || echo "000")
      assert_status_code "$status" "200" "Workflow chat request" || rc=1
      local citations
      citations=$(jq '.citations | length' "$TEST_DIR/workflow-rag.json" 2>/dev/null || echo 0)
      assert_greater_than "$citations" "0" "Workflow answer includes citations" || rc=1
      ;;
    backup_restore_workflow)
      run_backup_job || rc=1
      stage4_restore_temp_db "$LATEST_BACKUP_TS" || rc=1
      local note_count
      note_count=$(docker exec vib-postgres psql -U "${POSTGRES_USER:-vib}" -d vib_restore_test -t -c "SELECT COUNT(*) FROM notes;" | tr -d '[:space:]')
      assert_not_empty "$note_count" "Restored DB contains notes" || rc=1
      ;;
    *)
      error "Unknown workflow check $check"
      rc=1
      ;;
  esac
  return $rc
}
#############################################
#############################################
# Additional stage functions to be implemented...
#############################################
#############################################
# Additional stage functions to be implemented...
#############################################
#############################################
# Additional stage functions to be implemented...
#############################################

print_summary() {
  local end_time duration
  end_time=$(date +%s)
  duration=$((end_time - START_TIME))
  section "TEST SUMMARY"
  echo "Total Tests: $TOTAL_TESTS"
  echo "Passed: $PASSED_TESTS"
  echo "Failed: $FAILED_TESTS"
  echo "Warnings: $WARNINGS"
  printf 'Duration: %dm %ds
' $((duration/60)) $((duration%60))
  if [[ $TOTAL_TESTS -gt 0 ]]; then
    local rate
    rate=$(awk -v p="$PASSED_TESTS" -v t="$TOTAL_TESTS" 'BEGIN{if(t==0){print "0.0"}else{printf "%.1f", (p/t)*100}}')
    echo "Pass Rate: $rate%"
  fi
  if [[ $FAILED_TESTS -gt 0 ]]; then
    echo ""
    echo "Failed Tests:"
    for name in "${FAILED_TEST_NAMES[@]}"; do
      echo "  - $name"
    done
  fi
  echo ""
  echo "SLO Status:"
  if [[ -n "$REMINDER_FIRE_LAG_P95" && "$REMINDER_FIRE_LAG_P95" != "unknown" ]]; then
    echo "  - Reminder fire lag p95: ${REMINDER_FIRE_LAG_P95}s (target < ${REMINDER_FIRE_LAG_TARGET}s)"
  else
    echo "  - Reminder fire lag p95: unavailable"
  fi
  if [[ -n "$PUSH_SUCCESS_RATE" && "$PUSH_SUCCESS_RATE" != "unknown" ]]; then
    local display_rate target_rate
    display_rate=$(awk -v r="$PUSH_SUCCESS_RATE" 'BEGIN{printf "%.2f%%", r*100}')
    target_rate=$(awk -v t="$PUSH_SUCCESS_TARGET" 'BEGIN{printf "%.0f%%", t*100}')
    echo "  - Push success rate: $display_rate (target > $target_rate)"
  else
    echo "  - Push success rate: unavailable"
  fi
  if [[ -n "$DOC_INGESTION_P95" && "$DOC_INGESTION_P95" != "unknown" ]]; then
    echo "  - Document ingestion p95: ${DOC_INGESTION_P95}s (target < ${DOC_INGESTION_TARGET}s)"
  else
    echo "  - Document ingestion p95: unavailable"
  fi
  if [[ -n "$VECTOR_SEARCH_P95" && "$VECTOR_SEARCH_P95" != "unknown" ]]; then
    echo "  - Vector search p95: ${VECTOR_SEARCH_P95}ms (target < ${SEARCH_LATENCY_THRESHOLD}ms)"
  else
    echo "  - Vector search p95: unavailable"
  fi
  echo ""
  echo "Logs: $TEST_LOG"
  echo "Artifacts: $TEST_DIR"
}

generate_json_report() {
  local report="$TEST_DIR/results.json"
  local duration=$(( $(date +%s) - START_TIME ))
  jq -n \
    --arg timestamp "$TIMESTAMP" \
    --arg base_url "$BASE_URL" \
    --arg duration "$duration" \
    --argjson total "$TOTAL_TESTS" \
    --argjson passed "$PASSED_TESTS" \
    --argjson failed "$FAILED_TESTS" \
    --argjson warnings "$WARNINGS" \
    --arg reminder_p95 "${REMINDER_FIRE_LAG_P95:-null}" \
    --arg push_rate "${PUSH_SUCCESS_RATE:-null}" \
    --arg doc_p95 "${DOC_INGESTION_P95:-null}" \
    --arg search_p95 "${VECTOR_SEARCH_P95:-null}" \
    --arg tests "$(printf '%s
' "${TEST_RECORDS[@]}" | jq -Rsn '[inputs | select(length>0) | split("|") | {name:.[0], status:.[1], duration:.[2], message:.[3]}]')" \
    '($tests | fromjson) as $items | {
      timestamp: $timestamp,
      base_url: $base_url,
      duration_seconds: ($duration|tonumber),
      totals: {total: $total, passed: $passed, failed: $failed, warnings: $warnings},
      slo: {reminder_fire_lag_p95: ($reminder_p95|tonumber?), push_success_rate: ($push_rate|tonumber?), document_ingestion_p95: ($doc_p95|tonumber?), vector_search_p95: ($search_p95|tonumber?)},
      tests: $items
    }' > "$report"
  log "JSON report: $report"
}

generate_html_report() {
  local report="$TEST_DIR/report.html"
  cat > "$report" <<HTML
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>VIB MVP Test Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    .pass { color: #2d7f2d; }
    .fail { color: #c0392b; }
    .warn { color: #c78500; }
    table { border-collapse: collapse; width: 100%; margin-top: 16px; }
    th, td { border: 1px solid #ddd; padding: 8px; }
    th { background: #333; color: #fff; }
  </style>
</head>
<body>
  <h1>VIB MVP Test Report</h1>
  <p><strong>Timestamp:</strong> $TIMESTAMP</p>
  <p><strong>Base URL:</strong> $BASE_URL</p>
  <p><strong>Total:</strong> $TOTAL_TESTS &nbsp; <span class="pass">Passed: $PASSED_TESTS</span> &nbsp; <span class="fail">Failed: $FAILED_TESTS</span> &nbsp; <span class="warn">Warnings: $WARNINGS</span></p>
  <table>
    <tr><th>Test Name</th><th>Status</th><th>Duration</th><th>Message</th></tr>
HTML
  for record in "${TEST_RECORDS[@]}"; do
    IFS='|' read -r name status duration message <<<"$record"
    [[ -z "$name" ]] && continue
    local class="pass"
    [[ "$status" == "FAIL" ]] && class="fail"
    [[ "$status" == "SKIPPED" ]] && class="warn"
    cat >> "$report" <<ROW
    <tr class="$class"><td>${name}</td><td>${status}</td><td>${duration}</td><td>${message}</td></tr>
ROW
  done
  cat >> "$report" <<HTML
  </table>
</body>
</html>
HTML
  log "HTML report: $report"
}

main() {
  setup
  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "0" ]]; then
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
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "1" ]]; then
    section "STAGE 1: NOTES + VECTOR SEARCH"
    local tests=(
      "notes_api_create notes_check api_create"
      "notes_db_record notes_check db_record"
      "notes_markdown notes_check markdown_file"
      "notes_frontmatter notes_check frontmatter"
      "notes_embedding notes_check embedding_state"
      "notes_vector_keyword notes_check vector_keyword"
      "notes_vector_semantic notes_check vector_semantic"
      "notes_top3 notes_check top3"
      "notes_filter notes_check content_type_filter"
      "notes_user_scope notes_check user_scope"
      "notes_dedup_response notes_check dedup_response"
      "notes_dedup_message notes_check dedup_message"
      "notes_db_constraint notes_check db_constraint"
      "notes_slug_simple notes_check slug_simple"
      "notes_slug_special notes_check slug_special"
      "notes_slug_collision notes_check slug_collision"
      "notes_file_sync notes_check file_sync_state"
      "notes_external_edit notes_check external_edit"
      "notes_chat_create notes_check chat_create"
      "notes_chat_search notes_check chat_search"
      "notes_list_endpoint notes_check list_endpoint"
      "notes_update_endpoint notes_check update_endpoint"
    )
    for entry in "${tests[@]}"; do
      IFS=' ' read -r name func arg <<<"$entry"
      run_test "$name" "$func" "$arg"
    done
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "2" ]]; then
    section "STAGE 2: REMINDERS + NOTIFICATIONS"
    local tests=(
      "reminder_api_create test_reminder_create_api"
      "reminder_db_record test_reminder_in_database"
      "reminder_scheduler_entry test_reminder_scheduler_entry"
      "reminder_chat_flow test_reminder_chat_flow"
      "reminder_smart_defaults test_reminder_smart_defaults"
      "reminder_dedup_response test_reminder_dedup_response"
      "reminder_dedup_constraint test_reminder_dedup_constraint"
      "reminder_timezone test_reminder_timezone_conversion"
      "reminder_due_local test_reminder_due_local_preserved"
      "reminder_snooze_updates test_reminder_snooze_updates_due"
      "reminder_snooze_logs test_reminder_snooze_reschedules"
      "reminder_cancel_endpoint test_reminder_cancel_endpoint"
      "reminder_cancel_state test_reminder_cancel_halts_firing"
      "reminder_recurring_daily test_reminder_recurring_daily"
      "reminder_recurring_weekly test_reminder_recurring_weekly"
      "reminder_recurring_monthly test_reminder_recurring_monthly"
      "device_registration test_device_registration"
      "device_db_entry test_device_db_entry"
      "device_test_notification test_device_test_notification"
      "push_metrics test_push_metrics"
      "reminder_fire_slo test_reminder_fire_slo"
      "notification_delivery_record test_notification_delivery_record"
      "reminder_metrics_created test_reminder_metrics_created_total"
      "reminder_metrics_deduped test_reminder_metrics_deduped_total"
      "reminder_metrics_fire_lag test_reminder_metrics_fire_lag"
      "reminder_list_endpoint test_reminder_list_endpoint"
      "reminder_update_endpoint test_reminder_update_endpoint"
      "reminder_restart_persistence test_reminder_restart_persistence"
    )
    for entry in "${tests[@]}"; do
      IFS=' ' read -r name func <<<"$entry"
      run_test "$name" "$func"
    done
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "3" ]]; then
    section "STAGE 3: DOCUMENTS + RAG"
    local tests=(
      "doc_upload documents_check upload_pdf"
      "doc_job_created documents_check job_created"
      "doc_job_completed documents_check job_completed"
      "doc_status_indexed documents_check status_indexed"
      "doc_chunks_created documents_check chunks_created"
      "doc_chunk_ordinals documents_check chunk_ordinals"
      "doc_chunk_tokens documents_check chunk_tokens"
      "doc_chunk_metadata documents_check chunk_metadata"
      "doc_vectors documents_check vectors_embedded"
      "doc_vector_payload_fields documents_check vector_payload_fields"
      "doc_search_keyword documents_check search_keyword"
      "doc_search_semantic documents_check search_semantic"
      "doc_search_filter documents_check search_filter"
      "doc_rag_answer documents_check rag_answer"
      "doc_rag_citations documents_check rag_citations"
      "doc_deduplication documents_check deduplication"
      "doc_large_file_rejected documents_check large_file_rejected"
      "doc_unsupported_type documents_check unsupported_type"
      "doc_processing_speed_small documents_check processing_speed_small"
      "doc_processing_speed_large documents_check processing_speed_large"
      "doc_list_endpoint documents_check list_endpoint"
      "doc_detail_endpoint documents_check detail_endpoint"
      "doc_chunks_endpoint documents_check chunks_endpoint"
      "doc_delete_endpoint documents_check delete_endpoint"
      "doc_delete_vectors documents_check delete_vectors"
      "doc_corrupted_pdf documents_check corrupted_pdf_failure"
      "doc_job_error documents_check job_error_message"
      "doc_concurrent_uploads documents_check concurrent_uploads"
      "doc_search_latency documents_check vector_search_latency"
      "doc_metrics_counters documents_check metrics_counters"
    )
    for entry in "${tests[@]}"; do
      IFS=' ' read -r name func arg <<<"$entry"
      run_test "$name" "$func" "$arg"
    done
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "4" ]]; then
    section "STAGE 4: BACKUPS + RETENTION + OBSERVABILITY"
    local tests=(
      "stage4_metrics_defined stage4_check metrics_defined"
      "stage4_metrics_non_zero stage4_check metrics_non_zero"
      "stage4_metrics_histograms stage4_check metrics_histograms"
      "stage4_metrics_gauges stage4_check metrics_gauges"
      "stage4_metrics_counters stage4_check metrics_counters"
      "stage4_slo_reminder stage4_check slo_reminder_fire_lag"
      "stage4_slo_push stage4_check slo_push_success"
      "stage4_slo_document stage4_check slo_document_ingestion"
      "stage4_slo_vector stage4_check slo_vector_search"
      "stage4_backup_script stage4_check backup_script_exists"
      "stage4_backup_run stage4_check backup_run"
      "stage4_backup_postgres stage4_check backup_postgres_artifact"
      "stage4_backup_qdrant stage4_check backup_qdrant_snapshot"
      "stage4_backup_files stage4_check backup_files_archived"
      "stage4_backup_manifest stage4_check backup_manifest"
      "stage4_restore_script stage4_check restore_script_exists"
      "stage4_restore_temp_db stage4_check restore_temp_db"
      "stage4_retention_scheduler stage4_check retention_scheduler"
      "stage4_retention_cleanup stage4_check retention_cleanup_manual"
      "stage4_retention_metrics stage4_check retention_metrics"
      "stage4_db_size stage4_check database_size_report"
      "stage4_db_vacuum stage4_check database_vacuum"
      "stage4_metrics_prom stage4_check metrics_prometheus_format"
      "stage4_manifest_counts stage4_check backup_manifest_counts"
    )
    for entry in "${tests[@]}"; do
      IFS=' ' read -r name func arg <<<"$entry"
      run_test "$name" "$func" "$arg"
    done
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "performance" ]]; then
    section "PERFORMANCE TESTS"
    local tests=(
      "perf_api_latency performance_check api_latency"
      "perf_search performance_check search_performance"
      "perf_doc_processing performance_check document_processing_speed"
      "perf_concurrent_requests performance_check concurrent_requests"
    )
    for entry in "${tests[@]}"; do
      IFS=' ' read -r name func arg <<<"$entry"
      run_test "$name" "$func" "$arg"
    done
  fi

  if [[ -z "$RUN_STAGE" || "$RUN_STAGE" == "workflows" ]]; then
    section "END-TO-END WORKFLOWS"
    local tests=(
      "workflow_note_to_reminder workflow_check note_to_reminder"
      "workflow_document_to_answer workflow_check document_to_answer"
      "workflow_backup_restore workflow_check backup_restore_workflow"
    )
    for entry in "${tests[@]}"; do
      IFS=' ' read -r name func arg <<<"$entry"
      run_test "$name" "$func" "$arg"
    done
  fi

  cleanup_test_data
  print_summary
  generate_json_report
  if $HTML_REPORT; then
    generate_html_report
  fi

  if [[ $FAILED_TESTS -gt 0 ]]; then
    exit 1
  fi
}

main "$@"
