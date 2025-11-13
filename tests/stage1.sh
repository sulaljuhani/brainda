#!/usr/bin/env bash
# Stage 1: Notes + Vector Search Tests
# Tests note creation, markdown generation, vector embeddings, and semantic search

set -euo pipefail

# Enable debug mode if requested
if [[ "${DEBUG:-0}" == "1" ]]; then
  set -x
fi

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
      local response path note_id
      response=$(curl -sS -X POST "$BASE_URL/api/v1/notes" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"title":"Collision","body":"slug"}')
      path=$(echo "$response" | jq -r '.data.md_path // empty')
      note_id=$(echo "$response" | jq -r '.data.id // empty')
      if [[ "$path" =~ collision-[a-z0-9]{8}\.md ]]; then
        success "Slug collision resolved with suffix"
      else
        error "Slug collision not handled ($path)"
        rc=1
      fi
      if [[ -n "$note_id" ]]; then
        psql_query "DELETE FROM file_sync_state WHERE file_path = '$path';" >/dev/null 2>&1 || true
        psql_query "DELETE FROM notes WHERE id = '$note_id';" >/dev/null 2>&1 || true
        rm -f "vault/$path" >/dev/null 2>&1 || true
      fi
      rm -f "$collision"
      ;;
    file_sync_state)
      local count
      count=$(psql_query "SELECT COUNT(*) FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';" | tr -d '[:space:]')
      assert_equals "$count" "1" "file_sync_state entry exists" || rc=1
      ;;
    external_edit)
      local before after file="vault/$NOTE_FIXTURE_MD_PATH" backup="$TEST_DIR/external-edit-$TIMESTAMP.md"
      cp "$file" "$backup"
      before=$(psql_query "SELECT extract(epoch FROM last_embedded_at) FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';")
      echo "\nUpdated $(date)" >> "$file"
      wait_for "psql_query \"SELECT extract(epoch FROM last_embedded_at) FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';\" | awk -v before=$before 'NF && \$1 > before { exit 0 } END { exit 1 }'" 180 "re-embedding after external edit"
      after=$(psql_query "SELECT extract(epoch FROM last_embedded_at) FROM file_sync_state WHERE file_path = '$NOTE_FIXTURE_MD_PATH';")
      assert_greater_than "${after:-0}" "${before:-0}" "Embedding timestamp advanced" || rc=1
      cp "$backup" "$file"
      rm -f "$backup"
      ;;
    chat_create)
      mkdir -p "$TEST_DIR"
      local payload status response note_id md_path
      payload=$(jq -n --arg msg "Add a note titled Chat Driven with body Chat body" '{message:$msg}')
      status=$(curl -sS -o "$TEST_DIR/chat-note.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/chat" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" || echo "000")
      response=$(cat "$TEST_DIR/chat-note.json" 2>/dev/null || echo "")
      assert_status_code "$status" "200" "Chat endpoint responded" || rc=1
      assert_json_field "$response" '.mode' 'note' "Chat note mode returned" || rc=1
      assert_json_field "$response" '.data.id' '' "Chat note ID present" || rc=1
      note_id=$(echo "$response" | jq -r '.data.id // empty')
      md_path=$(echo "$response" | jq -r '.data.md_path // empty')
      if [[ -n "$note_id" ]]; then
        psql_query "DELETE FROM file_sync_state WHERE file_path = '$md_path';" >/dev/null 2>&1 || true
        psql_query "DELETE FROM notes WHERE id = '$note_id';" >/dev/null 2>&1 || true
        rm -f "vault/$md_path" >/dev/null 2>&1 || true
      fi
      ;;
    chat_search)
      mkdir -p "$TEST_DIR"
      local payload status response result_count
      payload=$(jq -n --arg msg "Search my notes for VIB" '{message:$msg}')
      status=$(curl -sS -o "$TEST_DIR/chat-search.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/chat" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" || echo "000")
      response=$(cat "$TEST_DIR/chat-search.json" 2>/dev/null || echo "")
      assert_status_code "$status" "200" "Chat search endpoint responded" || rc=1
      assert_json_field "$response" '.mode' 'search' "Chat search mode returned" || rc=1
      result_count=$(echo "$response" | jq '.data.results | length' 2>/dev/null || echo 0)
      assert_greater_than "$result_count" "0" "Chat search returned results" || rc=1
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

run_stage1() {
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
}
