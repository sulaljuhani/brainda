#!/usr/bin/env bash
# End-to-End Workflow Tests
# Tests complete workflows combining multiple features

set -euo pipefail

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

run_workflow_tests() {
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
}
