#!/usr/bin/env bash
# End-to-End Workflow Tests
# Tests complete workflows combining multiple features

set -euo pipefail
IFS=$'\n\t'

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
      local reminder_file="$TEST_DIR/workflow-reminder.json"
      local status rid
      status=$(curl -sS -o "$reminder_file" -w "%{http_code}" -X POST "$BASE_URL/api/v1/reminders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" || echo "000")
      assert_status_code "$status" "200" "Workflow reminder request" || rc=1
      rid=$(jq -r '.data.id // empty' "$reminder_file" 2>/dev/null || echo "")
      assert_not_empty "$rid" "Workflow reminder created" || rc=1
      local linked
      linked=$(psql_query "SELECT note_id FROM reminders WHERE id = '$rid';")
      assert_equals "${linked// /}" "$NOTE_FIXTURE_ID" "Reminder linked to note" || rc=1
      if [[ -n "$rid" ]]; then
        local delete_status
        delete_status=$(curl -sS -o /dev/null -w "%{http_code}" -X DELETE "$BASE_URL/api/v1/reminders/$rid" -H "Authorization: Bearer $TOKEN" || echo "000")
        assert_status_code "$delete_status" "200" "Workflow reminder cleanup" || rc=1
      fi
      ;;
    document_to_answer)
      ensure_document_fixture
      local payload status
      payload='{ "message": "What is covered in the integration document?" }'
      status=$(curl -sS -o "$TEST_DIR/workflow-rag.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/chat" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$payload" || echo "000")
      assert_status_code "$status" "200" "Workflow chat request" || rc=1
      local answer citations invalid_citations
      answer=$(jq -r '.answer // empty' "$TEST_DIR/workflow-rag.json" 2>/dev/null || echo "")
      assert_not_empty "$answer" "Workflow chat returned answer" || rc=1
      citations=$(jq '.citations | length' "$TEST_DIR/workflow-rag.json" 2>/dev/null || echo 0)
      assert_greater_than "$citations" "0" "Workflow answer includes citations" || rc=1
      invalid_citations=$(jq --arg doc "$DOC_ID" '[.citations[]? | select(.document_id != $doc)] | length' "$TEST_DIR/workflow-rag.json" 2>/dev/null || echo 0)
      assert_equals "$invalid_citations" "0" "Workflow citations reference document fixture" || rc=1
      ;;
    backup_restore_workflow)
      run_backup_job || rc=1
      assert_not_empty "${LATEST_BACKUP_TS:-}" "Backup timestamp discovered" || rc=1
      stage4_restore_temp_db "$LATEST_BACKUP_TS" || rc=1
      local note_count
      note_count=$(docker exec vib-postgres psql -U "${POSTGRES_USER:-vib}" -d vib_restore_test -t -c "SELECT COUNT(*) FROM notes;" | tr -d '[:space:]')
      assert_greater_than "${note_count:-0}" "0" "Restored DB contains notes" || rc=1
      docker exec vib-postgres psql -U "${POSTGRES_USER:-vib}" -d postgres -c "DROP DATABASE IF EXISTS vib_restore_test;" >/dev/null 2>&1 || {
        error "Failed to drop temporary restore database"
        rc=1
      }
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
