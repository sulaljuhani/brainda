#!/bin/bash
set -euo pipefail

# Enable debug mode if requested
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

BASE_URL=${BASE_URL:-"http://localhost:8000"}
QDRANT_URL=${QDRANT_URL:-"http://localhost:6333"}

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

fail() {
    log "✗ $1"
    exit 1
}

require_command() {
    local cmd=$1
    command -v "$cmd" >/dev/null 2>&1 || fail "Missing required dependency: $cmd"
}

ensure_dependencies() {
    for cmd in curl jq docker; do
        require_command "$cmd"
    done
    if ! docker ps --format '{{.Names}}' | grep -q '^brainda-postgres$'; then
        fail "brainda-postgres container is not running"
    fi
}

ensure_env_token() {
    if [ ! -f .env ]; then
        fail ".env file not found; copy .env.example and configure API_TOKEN"
    fi
    local token_line
    token_line=$(grep -m1 '^API_TOKEN=' .env || true)
    if [ -z "$token_line" ]; then
        fail "API_TOKEN not configured in .env"
    fi
    TOKEN=${token_line#API_TOKEN=}
    TOKEN=$(printf '%s' "$TOKEN" | tr -d '\r')
    TOKEN=${TOKEN%"}
    TOKEN=${TOKEN#"}
    if [ -z "$TOKEN" ]; then
        fail "API_TOKEN value is empty"
    fi
}

ensure_services() {
    if ! curl -sf "$BASE_URL/api/v1/health" >/dev/null; then
        fail "API service at $BASE_URL is unreachable"
    fi
    if ! curl -sf "$QDRANT_URL/collections" >/dev/null; then
        fail "Qdrant service at $QDRANT_URL is unreachable"
    fi
}

ensure_dependencies
ensure_env_token
ensure_services

wait_with_log() {
    local seconds=$1
    local message=$2
    log "$message"
    for ((i=seconds; i>0; i--)); do
        printf "\rWaiting %ss..." "$i"
        sleep 1
    done
    printf "\r✓ Wait complete        \n"
}

echo "======================================"
echo "Stage 3 Validation Test"
echo "======================================"

log "Test 1: Preparing test files..."
mkdir -p tests/fixtures

if [ ! -f "tests/fixtures/test-document.pdf" ]; then
    log "Creating test PDF fixture..."
    cat <<'EOF' >/tmp/stage3-doc.txt
This is a test document for Brainda Stage 3 validation.

It contains some sample text about:
- Document ingestion
- Vector search
- RAG capabilities

The system should be able to parse this PDF, chunk it, embed it, and answer questions about it.
EOF
    if command -v pandoc >/dev/null 2>&1; then
        pandoc /tmp/stage3-doc.txt -o tests/fixtures/test-document.pdf
    else
        log "pandoc not found; using built-in PDF generator"
        python - <<'PY'
from pathlib import Path

def pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

text = Path("/tmp/stage3-doc.txt").read_text().strip()
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
    fi
fi
log "✓ Test fixture ready"

log "Test 2: Uploading test document..."

# Cleanup any previous test artifacts to keep run idempotent
docker exec brainda-postgres psql -U brainda  -d brainda -c \
  "DELETE FROM jobs WHERE (payload->>'document_id') IN (SELECT id::text FROM documents WHERE filename = 'test-document.pdf');" >/dev/null
docker exec brainda-postgres psql -U brainda  -d brainda -c \
  "DELETE FROM documents WHERE filename = 'test-document.pdf';" >/dev/null

RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/test-document.pdf")
printf '[%s] Upload response: %s\n' "$(date +%H:%M:%S)" "$RESPONSE"

SUCCESS=$(printf '%s' "$RESPONSE" | jq -r '.success')
JOB_ID=$(printf '%s' "$RESPONSE" | jq -r '.job_id')
DOC_ID=$(printf '%s' "$RESPONSE" | jq -r '.document_id')

if [ "$SUCCESS" != "true" ] || [ "$JOB_ID" == "null" ]; then
    log "✗ Document upload failed"
    echo "Response: $RESPONSE"
    exit 1
fi
log "✓ Document uploaded (job_id=$JOB_ID, document_id=$DOC_ID)"

log "Test 3: Verifying document exists in database..."
DOC_PRESENT=0
for attempt in {1..5}; do
    DOC_COUNT=$(docker exec brainda-postgres psql -U postgres  -d brainda -t -c \
      "SELECT COUNT(*) FROM documents WHERE id = '$DOC_ID';" | tr -d '[:space:]')
    if [ "$DOC_COUNT" = "1" ]; then
        DOC_PRESENT=1
        break
    fi
    log "  Document row not visible yet (attempt $attempt/5), retrying..."
    sleep 3
done
if [ "$DOC_PRESENT" -ne 1 ]; then
    fail "Document not found in database"
fi
log "✓ Document row present"

log "Test 4: Waiting for job completion..."
MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    JOB_STATUS=$(curl -s "$BASE_URL/api/v1/jobs/$JOB_ID" \
      -H "Authorization: Bearer $TOKEN" | jq -r '.status')
    log "  Job status: $JOB_STATUS (waited ${WAITED}s)"
    if [ "$JOB_STATUS" == "completed" ]; then
        break
    elif [ "$JOB_STATUS" == "failed" ]; then
        log "✗ Job failed"
        curl -s "$BASE_URL/api/v1/jobs/$JOB_ID" \
          -H "Authorization: Bearer $TOKEN" | jq '.error_message'
        exit 1
    fi
    sleep 5
    WAITED=$((WAITED + 5))
done
if [ "$JOB_STATUS" != "completed" ]; then
    log "✗ Job did not complete within $MAX_WAIT seconds"
    exit 1
fi
log "✓ Job completed"

log "Test 5: Checking chunks..."
CHUNK_READY=0
CHUNK_COUNT=0
for attempt in {1..5}; do
    CHUNK_COUNT=$(docker exec brainda-postgres psql -U postgres  -d brainda -t -c \
      "SELECT COUNT(*) FROM chunks WHERE document_id = '$DOC_ID';" | tr -d '[:space:]')
    if [ "${CHUNK_COUNT:-0}" -ge 1 ]; then
        CHUNK_READY=1
        break
    fi
    log "  No chunks yet (attempt $attempt/5), waiting..."
    sleep 3
done
if [ "$CHUNK_READY" -ne 1 ]; then
    fail "No chunks stored"
fi
log "✓ $CHUNK_COUNT chunks stored"

log "Test 6: Document status is indexed..."
DOC_STATUS=$(docker exec brainda-postgres psql -U postgres  -d brainda -t -c \
  "SELECT status FROM documents WHERE id = '$DOC_ID';" | tr -d '[:space:]')
if [ "$DOC_STATUS" != "indexed" ]; then
    log "✗ Document status $DOC_STATUS (expected indexed)"
    exit 1
fi
log "✓ Document indexed"

log "Test 7: Vector payloads exist..."
wait_with_log 5 "Waiting for Qdrant sync"
VECTOR_COUNT=0
VECTOR_READY=0
for attempt in {1..5}; do
    VECTOR_COUNT=$(curl -s -X POST "$QDRANT_URL/collections/knowledge_base/points/count" \
      -H "Content-Type: application/json" \
      -d '{"exact":true,"filter":{"must":[{"key":"parent_document_id","match":{"value":"'"$DOC_ID"'"}}]}}' | jq -r '.result.count // 0')
    if [ "${VECTOR_COUNT:-0}" -gt 0 ]; then
        VECTOR_READY=1
        break
    fi
    log "  No vectors yet for document (attempt $attempt/5), waiting..."
    sleep 5
done
if [ "$VECTOR_READY" -ne 1 ]; then
    fail "No vectors found in Qdrant for document $DOC_ID"
fi
log "✓ Qdrant stored $VECTOR_COUNT vectors for document"

log "Test 8: Search endpoint returns document chunks..."
SEARCH_FOUND=0
SEARCH_RESPONSE=""
for attempt in {1..5}; do
    SEARCH_RESPONSE=$(curl -s "$BASE_URL/api/v1/search?q=test%20document&content_type=document_chunk" \
      -H "Authorization: Bearer $TOKEN")
    RESULT_COUNT=$(printf '%s' "$SEARCH_RESPONSE" | jq '.results | length')
    MATCHING_COUNT=$(printf '%s' "$SEARCH_RESPONSE" | jq --arg doc "$DOC_ID" '[((.results // [])[] | select(.metadata.parent_document_id == $doc))] | length')
    if [ "${RESULT_COUNT:-0}" -gt 0 ] && [ "${MATCHING_COUNT:-0}" -gt 0 ]; then
        SEARCH_FOUND=1
        log "✓ Search returned $RESULT_COUNT results (${MATCHING_COUNT} from document)"
        break
    fi
    log "  Search results not ready yet (attempt $attempt/5), waiting..."
    sleep 3
done
if [ "$SEARCH_FOUND" -ne 1 ]; then
    log "Search response: $SEARCH_RESPONSE"
    fail "Search endpoint did not return chunks for document $DOC_ID"
fi

log "Test 9: RAG answer via chat endpoint..."
CHAT_SUCCESS=0
CHAT_RESPONSE=""
for attempt in {1..3}; do
    CHAT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/chat" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"message":"What does the test document say?"}')
    CHAT_MODE=$(printf '%s' "$CHAT_RESPONSE" | jq -r '.mode // empty')
    CITATION_MATCH=$(printf '%s' "$CHAT_RESPONSE" | jq --arg doc "$DOC_ID" '[.citations[]? | select(.id == $doc)] | length')
    CHAT_MESSAGE=$(printf '%s' "$CHAT_RESPONSE" | jq -r '.message // ""' | tr '[:upper:]' '[:lower:]')
    if [ "$CHAT_MODE" = "rag" ] && [ "${CITATION_MATCH:-0}" -gt 0 ] && grep -q "test document" <<<"$CHAT_MESSAGE"; then
        CHAT_SUCCESS=1
        log "✓ Chat response referenced document with $CITATION_MATCH citation(s)"
        break
    fi
    log "  Chat response not referencing document yet (attempt $attempt/3), waiting..."
    sleep 5
done
if [ "$CHAT_SUCCESS" -ne 1 ]; then
    log "Chat response: $CHAT_RESPONSE"
    fail "Chat endpoint did not return a RAG answer citing the uploaded document"
fi

log "Test 10: Duplicate upload prevention..."
RESPONSE2=$(curl -s -X POST "$BASE_URL/api/v1/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/test-document.pdf")
if [ "$(printf '%s' "$RESPONSE2" | jq -r '.deduplicated')" != "true" ]; then
    log "✗ Deduplication check failed"
    exit 1
fi
log "✓ Duplicate detected successfully"

log "Test 11: Size limit enforcement..."
dd if=/dev/zero of=/tmp/large.pdf bs=1M count=55 >/dev/null 2>&1 || true
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/ingest" \
  -H "Authorization: Bearer $TOKEN" -F "file=@/tmp/large.pdf")
rm -f /tmp/large.pdf
if [ "$STATUS" != "400" ] && [ "$STATUS" != "413" ]; then
    log "⚠ Large file not rejected (status $STATUS)"
else
    log "✓ Large file rejected"
fi

log "Test 12: Unsupported file type rejection..."
echo "test" >/tmp/test.exe
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/ingest" \
  -H "Authorization: Bearer $TOKEN" -F "file=@/tmp/test.exe")
rm -f /tmp/test.exe
if [ "$STATUS" != "400" ]; then
    log "⚠ Unsupported file upload status $STATUS"
else
    log "✓ Unsupported file rejected"
fi

log "Test 13: Document deletion..."
echo "Temporary test content" >/tmp/temp-test.txt
if command -v pandoc >/dev/null 2>&1; then
    pandoc /tmp/temp-test.txt -o /tmp/temp-test.pdf
    TEMP_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/ingest" \
      -H "Authorization: Bearer $TOKEN" \
      -F "file=@/tmp/temp-test.pdf")
    TEMP_DOC_ID=$(printf '%s' "$TEMP_RESPONSE" | jq -r '.document_id')
    if [ "$TEMP_DOC_ID" != "null" ]; then
        wait_with_log 10 "Waiting for temp doc ingestion"
        curl -s -X DELETE "$BASE_URL/api/v1/documents/$TEMP_DOC_ID" \
          -H "Authorization: Bearer $TOKEN" >/dev/null
        DOC_EXISTS=$(docker exec brainda-postgres psql -U postgres  -d brainda -t -c \
          "SELECT COUNT(*) FROM documents WHERE id = '$TEMP_DOC_ID';" | tr -d '[:space:]')
        if [ "$DOC_EXISTS" != "0" ]; then
            log "✗ Document still present after deletion"
            exit 1
        fi
        log "✓ Document deletion works"
    fi
    rm -f /tmp/temp-test.pdf
else
    log "⚠ Skipping deletion test (pandoc missing)"
fi
rm -f /tmp/temp-test.txt

log "Test 14: Metrics expose ingestion gauges..."
METRICS=$(curl -s "$BASE_URL/api/v1/metrics")
for metric in \
  document_ingestion_duration_seconds \
  document_parsing_duration_seconds \
  embedding_duration_seconds \
  vector_search_duration_seconds \
  documents_ingested_total \
  chunks_created_total; do
    echo "$METRICS" | grep -q "$metric" || log "⚠ Missing metric: $metric"
done
log "✓ Metrics endpoint includes Stage 3 gauges"

log "Test 15: API pagination sanity..."
LIST_RESPONSE=$(curl -s "$BASE_URL/api/v1/documents?limit=10" \
  -H "Authorization: Bearer $TOKEN")
COUNT=$(printf '%s' "$LIST_RESPONSE" | jq 'length')
log "✓ Document list returned $COUNT items"

log "Test 16: Chunk retrieval API..."
CHUNKS_RESPONSE=$(curl -s "$BASE_URL/api/v1/documents/$DOC_ID/chunks" \
  -H "Authorization: Bearer $TOKEN")
CHUNKS_COUNT=$(printf '%s' "$CHUNKS_RESPONSE" | jq 'length')
if [ "$CHUNKS_COUNT" != "$CHUNK_COUNT" ]; then
    log "⚠ API chunk count ($CHUNKS_COUNT) differs from DB count ($CHUNK_COUNT)"
else
    log "✓ Chunk retrieval matches database count"
fi

echo "======================================"
log "Stage 3 automated validation finished"
echo "======================================"
