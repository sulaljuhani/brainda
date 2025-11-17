#!/usr/bin/env bash
# Restore Brainda data from a backup set created by backup.sh

set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARN: $*" >&2; }
fail() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; }
success() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ $*"; }

usage() {
  cat <<USAGE
Usage: $0 <TIMESTAMP>
Example: $0 20250201-020000

TIMESTAMP must match the suffix used in backup filenames (backup-<TIMESTAMP>.dump).
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

TIMESTAMP=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUESTED_BACKUP_DIR=${BACKUP_DIR:-/backups}
if [[ -d "$REQUESTED_BACKUP_DIR" ]]; then
  BACKUP_ROOT="$REQUESTED_BACKUP_DIR"
elif mkdir -p "$REQUESTED_BACKUP_DIR" >/dev/null 2>&1; then
  BACKUP_ROOT="$REQUESTED_BACKUP_DIR"
else
  BACKUP_ROOT="$SCRIPT_DIR"
  warn "Using $BACKUP_ROOT because $REQUESTED_BACKUP_DIR is unavailable"
fi
PGDUMP_FILE="$BACKUP_ROOT/postgres/backup-$TIMESTAMP.dump"
VAULT_ARCHIVE="$BACKUP_ROOT/files/vault-$TIMESTAMP.tar.gz"
UPLOADS_ARCHIVE="$BACKUP_ROOT/files/uploads-$TIMESTAMP.tar.gz"
REQUESTED_SNAPSHOT="$BACKUP_ROOT/qdrant/snapshot-$TIMESTAMP.tar.gz"
SNAPSHOT_FILE=""

POSTGRES_CONTAINER=${POSTGRES_CONTAINER:-brainda-postgres}
PG_USER=${POSTGRES_USER:-postgres}
PG_DB=${POSTGRES_DB:-vib}
QDRANT_URL=${QDRANT_URL:-http://localhost:6333}
QDRANT_COLLECTION=${QDRANT_COLLECTION:-knowledge_base}
# Resolve data directories relative to repo when not explicitly provided
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT_DIR=${VAULT_DIR:-"$REPO_ROOT/vault"}
UPLOADS_DIR=${UPLOADS_DIR:-"$REPO_ROOT/uploads"}
COMPOSE_CMD=${COMPOSE_CMD:-docker compose}
# Respect empty SERVICES_TO_STOP when explicitly provided
if [[ -z "${SERVICES_TO_STOP+x}" ]]; then
  SERVICES_TO_STOP="orchestrator worker beat"
fi

require_file() {
  local file=$1
  if [[ ! -f "$file" ]]; then
    fail "Missing required file: $file"
    exit 1
  fi
}

require_file "$PGDUMP_FILE"
require_file "$VAULT_ARCHIVE"
require_file "$UPLOADS_ARCHIVE"

if [[ -f "$REQUESTED_SNAPSHOT" ]]; then
  SNAPSHOT_FILE="$REQUESTED_SNAPSHOT"
else
  latest=$(ls -1 "$BACKUP_ROOT/qdrant"/snapshot-*.tar.gz 2>/dev/null | sort | tail -n1 || true)
  if [[ -n "$latest" ]]; then
    warn "No Qdrant snapshot for $TIMESTAMP, using latest ($latest)"
    SNAPSHOT_FILE="$latest"
  else
    warn "No Qdrant snapshots available; vector store will need reindexing"
  fi
fi

log "Restoring from timestamp $TIMESTAMP"
# Auto-confirm in non-interactive contexts or when ASSUME_YES=1
if [[ "${ASSUME_YES:-}" == "1" || ! -t 0 ]]; then
  CONFIRM="yes"
else
  read -r -p "This will overwrite current data. Continue? [yes/no]: " CONFIRM
fi
if [[ "$CONFIRM" != "yes" ]]; then
  log "Restore aborted"
  exit 0
fi

# -------------------------------------------
# Stop app services
# -------------------------------------------
log "Stopping application services ($SERVICES_TO_STOP)..."
if ! $COMPOSE_CMD stop $SERVICES_TO_STOP 2>/dev/null; then
  warn "Failed to stop some services (they may not be running)"
fi

# -------------------------------------------
# Restore Postgres
# -------------------------------------------
log "Restoring Postgres database $PG_DB..."
if ! docker exec "$POSTGRES_CONTAINER" psql -U "$PG_USER" -c "SELECT 1" >/dev/null 2>&1; then
  fail "Cannot connect to Postgres container '$POSTGRES_CONTAINER'"
  exit 1
fi

if ! docker exec "$POSTGRES_CONTAINER" psql -U "$PG_USER" -c "DROP DATABASE IF EXISTS $PG_DB WITH (FORCE);"; then
  warn "DROP DATABASE WITH FORCE failed, attempting regular drop"
  docker exec "$POSTGRES_CONTAINER" psql -U "$PG_USER" -c "DROP DATABASE IF EXISTS $PG_DB;"
fi

docker exec "$POSTGRES_CONTAINER" psql -U "$PG_USER" -c "CREATE DATABASE $PG_DB;"
if docker exec -i "$POSTGRES_CONTAINER" pg_restore -U "$PG_USER" -d "$PG_DB" -v <"$PGDUMP_FILE"; then
  success "Postgres restored"
else
  fail "pg_restore failed"
  exit 1
fi

# -------------------------------------------
# Restore Qdrant snapshot (optional)
# -------------------------------------------
if [[ -n "$SNAPSHOT_FILE" ]]; then
  log "Restoring Qdrant snapshot $(basename "$SNAPSHOT_FILE")..."
  SNAPSHOT_NAME=$(basename "$SNAPSHOT_FILE" .tar.gz)
  SNAPSHOT_NAME=${SNAPSHOT_NAME#snapshot-}
  if curl -sS -X POST "$QDRANT_URL/collections/$QDRANT_COLLECTION/snapshots/upload" \
      -F "snapshot=@$SNAPSHOT_FILE" >/dev/null; then
    if curl -sS -X PUT "$QDRANT_URL/collections/$QDRANT_COLLECTION/snapshots/$SNAPSHOT_NAME/recover" >/dev/null; then
      success "Qdrant restored"
    else
      warn "Snapshot uploaded but recover call failed"
    fi
  else
    warn "Failed to upload snapshot to Qdrant"
  fi
else
  warn "Skipping Qdrant restore; rebuild embeddings manually"
fi

# -------------------------------------------
# Restore vault/uploads
# -------------------------------------------
restore_archive() {
  local archive=$1
  local target=$2
  if [[ ! -f "$archive" ]]; then
    warn "Archive not found: $archive"
    return
  fi
  if [[ -z "$target" || "$target" == "/" ]]; then
    fail "Refusing to extract into $target"
    exit 1
  fi
  local parent
  parent=$(dirname "$target")
  mkdir -p "$parent"
  if [[ -d "$target" ]]; then
    find "$target" -mindepth 1 -delete
  fi
  tar -xzf "$archive" -C "$parent"
  success "Restored $(basename "$target")"
}

log "Restoring vault files..."
restore_archive "$VAULT_ARCHIVE" "$VAULT_DIR"
log "Restoring uploads..."
restore_archive "$UPLOADS_ARCHIVE" "$UPLOADS_DIR"

# -------------------------------------------
# Restart services
# -------------------------------------------
log "Starting application services..."
if ! $COMPOSE_CMD up -d $SERVICES_TO_STOP 2>/dev/null; then
  warn "Services failed to start via compose; start manually if needed"
fi

log "Waiting for services to settle..."
sleep 10

# -------------------------------------------
# Verify basic health
# -------------------------------------------
HEALTH_ENDPOINT=${HEALTH_ENDPOINT:-http://localhost:8000/api/v1/health}
if command -v curl >/dev/null 2>&1; then
  STATUS=$(curl -s "$HEALTH_ENDPOINT" | python3 -c 'import json,sys; 
try:
    data=json.load(sys.stdin)
    print(data.get("status"))
except Exception:
    pass' || true)
  if [[ "$STATUS" == "healthy" ]]; then
    success "Health check reports healthy"
  else
    warn "Health endpoint returned '$STATUS'"
  fi
else
  warn "curl not available; skipping health check"
fi

log "Restore workflow complete"
