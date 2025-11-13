#!/usr/bin/env bash
# Stage 3: Documents + RAG Tests
# Tests document ingestion, chunking, vector search, and RAG responses

set -euo pipefail
IFS=$'\n\t'

generate_pdf_with_pages() {
  local path="$1"
  local pages="$2"

  # Check if fpdf is available, if not, create a minimal valid PDF
  if ! python3 -c "import fpdf" >/dev/null 2>&1; then
    warn "fpdf not available, creating minimal PDF instead"
    # Create a minimal valid PDF
    cat > "$path" <<'EOF'
%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 12 Tf 72 720 Td (VIB test page) Tj ET
endstream endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000262 00000 n
0000000355 00000 n
trailer<</Size 6/Root 1 0 R>>
startxref
434
%%EOF
EOF
    return 0
  fi

  python3 - <<PY
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
  local context="${3:-}"
  local expected_status="${4:-completed}"
  local waited=0
  local status="pending"
  local response label
  label="Job $job_id"
  if [[ -n "$context" ]]; then
    label="$context (job $job_id)"
  fi
  while [[ $waited -lt $timeout ]]; do
    response=$(curl -sS -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/v1/jobs/$job_id")
    status=$(echo "$response" | jq -r '.status')
    if [[ "$status" == "$expected_status" ]]; then
      if [[ "$expected_status" == "failed" ]]; then
        LAST_JOB_ERROR=$(echo "$response" | jq -r '.error_message // ""')
      else
        LAST_JOB_ERROR=""
      fi
      return 0
    fi
    if [[ "$status" == "failed" ]]; then
      LAST_JOB_ERROR=$(echo "$response" | jq -r '.error_message // ""')
      error "$label failed (error=${LAST_JOB_ERROR:-unknown})"
      return 1
    fi
    if [[ "$status" == "completed" && "$expected_status" == "failed" ]]; then
      LAST_JOB_ERROR=""
      error "$label completed but failure was expected"
      return 1
    fi
    sleep 5
    waited=$((waited + 5))
  done
  LAST_JOB_ERROR="timeout"
  error "$label timed out after ${timeout}s waiting for status '$expected_status'"
  return 1
}

document_upload_file() {
  local file_path="$1"
  local mime="$2"
  local response doc_id job_id
  response=$(curl -sS --max-time 60 -X POST "$BASE_URL/api/v1/ingest" -H "Authorization: Bearer $TOKEN" -F "file=@$file_path;type=$mime")
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
    document_wait_for_job "$DOC_TWENTY_JOB_ID" 240 "20-page document fixture" || return 1
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
    document_wait_for_job "$DOC_FAILED_JOB_ID" 120 "corrupted document fixture" "failed"
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
      local response status response_file
      response_file="$TEST_DIR/search-keyword.json"
      status=$(curl -sS -o "$response_file" -w "%{http_code}" -G -H "Authorization: Bearer $TOKEN" \
        --data-urlencode "q=integration" \
        "$BASE_URL/api/v1/search")
      assert_status_code "$status" "200" "Keyword search HTTP 200" || rc=1
      response=$(cat "$response_file")
      assert_contains "$response" "$DOC_FILENAME" "Keyword search finds document" || rc=1
      ;;
    search_semantic)
      local response status response_file
      response_file="$TEST_DIR/search-semantic.json"
      status=$(curl -sS -o "$response_file" -w "%{http_code}" -G -H "Authorization: Bearer $TOKEN" \
        --data-urlencode "q=knowledge base document" \
        "$BASE_URL/api/v1/search")
      assert_status_code "$status" "200" "Semantic search HTTP 200" || rc=1
      response=$(cat "$response_file")
      assert_contains "$response" "$DOC_FILENAME" "Semantic search returns document" || rc=1
      ;;
    search_filter)
      local count status response_file
      response_file="$TEST_DIR/search-filter.json"
      status=$(curl -sS -o "$response_file" -w "%{http_code}" "$BASE_URL/api/v1/search?q=test&content_type=document_chunk" -H "Authorization: Bearer $TOKEN")
      assert_status_code "$status" "200" "Search filter HTTP 200" || rc=1
      count=$(jq '.results | length' "$response_file" 2>/dev/null || echo 0)
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
      local response flag job_id
      response=$(curl -sS -X POST "$BASE_URL/api/v1/ingest" -H "Authorization: Bearer $TOKEN" -F "file=@tests/fixtures/$DOC_FILENAME")
      flag=$(echo "$response" | jq -r '.deduplicated // false')
      job_id=$(echo "$response" | jq -r '.job_id // empty')
      if [[ -n "$job_id" && "$job_id" != "null" ]]; then
        document_wait_for_job "$job_id" 120 "duplicate upload job" || rc=1
      fi
      assert_equals "$flag" "true" "Duplicate upload flagged" || rc=1
      ;;
    large_file_rejected)
      ensure_large_document_fixture
      local status
      status=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/ingest" -H "Authorization: Bearer $TOKEN" -F "file=@$TEST_DIR/$DOC_LARGE_FILENAME;type=application/pdf")
      assert_status_code "$status" "422" "Large file rejected" || rc=1
      rm -f "$TEST_DIR/$DOC_LARGE_FILENAME" 2>/dev/null || true
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
      local before after temp_pair temp_id temp_job_id
      temp_pair=$(document_upload_file "tests/fixtures/$DOC_FILENAME" "application/pdf")
      temp_id=${temp_pair%%|*}
      temp_job_id=${temp_pair##*|}
      if [[ -n "$temp_pair" ]]; then
        if [[ -n "$temp_job_id" && "$temp_job_id" != "null" ]]; then
          if ! document_wait_for_job "$temp_job_id" 120 "delete vectors fixture"; then
            rc=1
            return $rc
          fi
        fi
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
      rm -f "$TEST_DIR"/concurrent-*.pdf "$TEST_DIR"/concurrent-*.status 2>/dev/null || true
      local pids=()
      for i in 1 2 3; do
        (
          local path="$TEST_DIR/concurrent-$i.pdf"
          generate_pdf_with_pages "$path" 2
          response=$(document_upload_file "$path" "application/pdf")
          [[ -z "${response%%|*}" ]] && echo "fail" > "$TEST_DIR/concurrent-$i.status"
        ) &
        pids+=($!)
      done

      # Wait for all uploads to complete with timeout protection
      local wait_timeout=120
      local wait_start=$(date +%s)
      local all_done=false
      while true; do
        # Check if all background jobs are done
        if ! jobs -r | grep -q .; then
          all_done=true
          break
        fi

        # Check for timeout
        local wait_elapsed=$(($(date +%s) - wait_start))
        if [[ $wait_elapsed -ge $wait_timeout ]]; then
          error "Timeout waiting for concurrent uploads to complete (${wait_timeout}s)"
          # Kill any remaining background jobs
          for pid in "${pids[@]}"; do
            kill -TERM "$pid" 2>/dev/null || true
          done
          wait 2>/dev/null || true
          rc=1
          break
        fi

        sleep 0.5
      done

      # Wait for all processes to ensure proper cleanup
      if [[ "$all_done" == "true" ]]; then
        for pid in "${pids[@]}"; do
          wait "$pid" 2>/dev/null || true
        done
      fi

      failures=$(grep -c "fail" "$TEST_DIR"/concurrent-*.status 2>/dev/null || true)
      assert_equals "${failures:-0}" "0" "Concurrent uploads succeed" || rc=1
      rm -f "$TEST_DIR"/concurrent-*.pdf "$TEST_DIR"/concurrent-*.status 2>/dev/null || true
      ;;
    vector_search_latency)
      local latency
      latency=$(measure_latency "/api/v1/search?q=document" 5)
      VECTOR_SEARCH_P95="$latency"
      assert_less_than "$latency" "$SEARCH_LATENCY_THRESHOLD" "Search latency under threshold" || rc=1
      ;;
    metrics_counters)
      local before after temp_pair temp_job_id
      before=$(document_latest_metric "documents_ingested_total" || echo 0)
      temp_pair=$(document_upload_file "tests/fixtures/$DOC_FILENAME" "application/pdf")
      temp_job_id=${temp_pair##*|}
      if [[ -n "$temp_job_id" && "$temp_job_id" != "null" ]]; then
        document_wait_for_job "$temp_job_id" 120 "metrics counter upload" || rc=1
      fi
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

run_stage3() {
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
}
