#!/usr/bin/env bash
#
# VIB Atomic Backup Script
# ------------------------
# Creates coordinated backups for Postgres, Qdrant, and filesystem data.
# Intended to be run nightly via cron or systemd timer.
#
set -euo pipefail

umask 027

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

fail() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

success() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ $*"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUESTED_BACKUP_DIR=${BACKUP_DIR:-/backups}
if mkdir -p "$REQUESTED_BACKUP_DIR" >/dev/null 2>&1; then
  BACKUP_ROOT="$REQUESTED_BACKUP_DIR"
else
  BACKUP_ROOT="$SCRIPT_DIR"
  log "Falling back to $BACKUP_ROOT (set BACKUP_DIR to override)"
fi
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RETENTION_DAYS=${RETENTION_DAYS:-30}
RETENTION_WEEKS=${RETENTION_WEEKS:-4}
RETENTION_SNAPSHOT_DAYS=$((RETENTION_WEEKS * 7))

PG_HOST=${PGHOST:-postgres}
PG_PORT=${PGPORT:-5432}
PG_USER=${POSTGRES_USER:-postgres}
PG_DB=${POSTGRES_DB:-vib}
PG_PASSWORD=${POSTGRES_PASSWORD:-${PGPASSWORD:-change-me-in-production}}

# Prefer dumping via Docker to avoid requiring pg_dump on host
POSTGRES_CONTAINER=${POSTGRES_CONTAINER:-vib-postgres}

## Default to localhost so backup can run from host without container DNS
QDRANT_URL=${QDRANT_URL:-http://localhost:6333}
# If environment provides a container URL like http://qdrant:6333, rewrite to localhost
if [[ "$QDRANT_URL" == http://qdrant* ]]; then
  QDRANT_URL="${QDRANT_URL/qdrant/localhost}"
fi
QDRANT_COLLECTION=${QDRANT_COLLECTION:-knowledge_base}

# Resolve data directories relative to repo when not explicitly provided
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT_DIR=${VAULT_DIR:-"$REPO_ROOT/vault"}
UPLOADS_DIR=${UPLOADS_DIR:-"$REPO_ROOT/uploads"}

POSTGRES_DIR="$BACKUP_ROOT/postgres"
QDRANT_DIR="$BACKUP_ROOT/qdrant"
FILES_DIR="$BACKUP_ROOT/files"
MANIFEST="$BACKUP_ROOT/manifest-$TIMESTAMP.txt"

mkdir -p "$POSTGRES_DIR" "$QDRANT_DIR" "$FILES_DIR"

declare -A FILE_SIZES

log "Starting backup run: $TIMESTAMP"

# -------------------------------------------
# 1. Postgres backup
# -------------------------------------------
log "Backing up Postgres ($PG_HOST/$PG_DB)..."
PGDUMP_FILE="$POSTGRES_DIR/backup-$TIMESTAMP.dump"
export PGPASSWORD="$PG_PASSWORD"
if command -v pg_dump >/dev/null 2>&1; then
  if pg_dump -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -Fc -f "$PGDUMP_FILE"; then
    FILE_SIZES[postgres]=$(du -h "$PGDUMP_FILE" | cut -f1)
    success "Postgres dump complete (${FILE_SIZES[postgres]})"
  else
    fail "pg_dump failed"
    exit 1
  fi
else
  # Fallback: stream pg_dump from Postgres container to host file
  if docker exec "$POSTGRES_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -c 'SELECT 1' >/dev/null 2>&1; then
    if docker exec -i "$POSTGRES_CONTAINER" pg_dump -U "$PG_USER" -d "$PG_DB" -Fc > "$PGDUMP_FILE"; then
      FILE_SIZES[postgres]=$(du -h "$PGDUMP_FILE" | cut -f1)
      success "Postgres dump complete via container (${FILE_SIZES[postgres]})"
    else
      fail "docker exec pg_dump failed"
      exit 1
    fi
  else
    fail "Cannot reach Postgres (container: $POSTGRES_CONTAINER)"
    exit 1
  fi
fi

# -------------------------------------------
# 2. Qdrant snapshot
# -------------------------------------------
log "Requesting Qdrant snapshot for collection '$QDRANT_COLLECTION'..."
SNAPSHOT_RESPONSE=$(curl -sS -X POST "$QDRANT_URL/collections/$QDRANT_COLLECTION/snapshots" \
  -H "Content-Type: application/json" \
  -d "{\"snapshot_name\": \"$TIMESTAMP\"}") || true
SNAPSHOT_NAME=$(SNAPSHOT_RESPONSE="$SNAPSHOT_RESPONSE" python3 - <<'PY'
import json, os
payload = os.environ.get('SNAPSHOT_RESPONSE')
try:
    data = json.loads(payload)
    result = data.get('result') or {}
    name = result.get('name') or result.get('snapshot')
    if name:
        print(name)
except Exception:
    pass
PY
)
unset SNAPSHOT_RESPONSE
if [[ -z "$SNAPSHOT_NAME" ]]; then
  fail "Qdrant snapshot creation failed"
  exit 1
fi
sleep 5
SNAPSHOT_FILE="$QDRANT_DIR/snapshot-$TIMESTAMP.tar.gz"
if curl -sS "$QDRANT_URL/collections/$QDRANT_COLLECTION/snapshots/$SNAPSHOT_NAME" -o "$SNAPSHOT_FILE"; then
  FILE_SIZES[qdrant]=$(du -h "$SNAPSHOT_FILE" | cut -f1)
  success "Qdrant snapshot saved (${FILE_SIZES[qdrant]})"
else
  fail "Unable to download Qdrant snapshot ($SNAPSHOT_NAME)"
  exit 1
fi

# -------------------------------------------
# 3. Filesystem archives
# -------------------------------------------
backup_dir() {
  local source=$1
  local label=$2
  local target="$FILES_DIR/$label-$TIMESTAMP.tar.gz"
  if [[ -d "$source" ]]; then
    tar -czf "$target" -C "$(dirname "$source")" "$(basename "$source")"
    FILE_SIZES[$label]=$(du -h "$target" | cut -f1)
    success "$label archive complete (${FILE_SIZES[$label]})"
  else
    fail "Directory not found: $source"
  fi
}

log "Archiving vault and uploads..."
backup_dir "$VAULT_DIR" "vault"
backup_dir "$UPLOADS_DIR" "uploads"

# -------------------------------------------
# 4. Cleanup old backups
# -------------------------------------------
log "Pruning backups older than $RETENTION_DAYS days..."
find "$POSTGRES_DIR" -name 'backup-*.dump' -mtime +"$RETENTION_DAYS" -print -delete | sed 's/^/  deleted /' || true
find "$FILES_DIR" -name '*.tar.gz' -mtime +"$RETENTION_DAYS" -print -delete | sed 's/^/  deleted /' || true
find "$QDRANT_DIR" -name 'snapshot-*.tar.gz' -mtime +"$RETENTION_SNAPSHOT_DAYS" -print -delete | sed 's/^/  deleted /' || true

# -------------------------------------------
# 5. Verify artifacts
# -------------------------------------------
log "Verifying backup artifacts..."
if command -v pg_restore >/dev/null 2>&1; then
  if pg_restore -l "$PGDUMP_FILE" >/dev/null 2>&1; then
    success "Postgres dump verified"
  else
    fail "Postgres dump verification failed"
    exit 1
  fi
else
  if docker exec -i "$POSTGRES_CONTAINER" pg_restore -l 2>/dev/null <"$PGDUMP_FILE" >/dev/null; then
    success "Postgres dump verified via container"
  else
    fail "Postgres dump verification failed (container)"
    exit 1
  fi
fi
for archive in "$FILES_DIR"/*-$TIMESTAMP.tar.gz; do
  [[ -f "$archive" ]] || continue
  if tar -tzf "$archive" >/dev/null 2>&1; then
    success "$(basename "$archive") verified"
  else
    fail "Corrupt archive: $archive"
    exit 1
  fi
done

# -------------------------------------------
# 6. Manifest
# -------------------------------------------
log "Writing manifest $MANIFEST"
cat >"$MANIFEST" <<MANIFEST
VIB Backup Manifest
===================
Timestamp: $TIMESTAMP
Date: $(date)

Files:
- Postgres: $(basename "$PGDUMP_FILE") (${FILE_SIZES[postgres]:-unknown})
- Qdrant: $(basename "$SNAPSHOT_FILE") (${FILE_SIZES[qdrant]:-unknown})
- Vault: vault-$TIMESTAMP.tar.gz (${FILE_SIZES[vault]:-unknown})
- Uploads: uploads-$TIMESTAMP.tar.gz (${FILE_SIZES[uploads]:-unknown})

Retention:
- Postgres: $RETENTION_DAYS days
- Files: $RETENTION_DAYS days
- Qdrant: $RETENTION_WEEKS weeks

Counts:
- Postgres dumps: $(find "$POSTGRES_DIR" -maxdepth 1 -name 'backup-*.dump' | wc -l)
- Qdrant snapshots: $(find "$QDRANT_DIR" -maxdepth 1 -name 'snapshot-*.tar.gz' | wc -l)
- File archives: $(find "$FILES_DIR" -maxdepth 1 -name '*.tar.gz' | wc -l)
MANIFEST
success "Manifest written"

log "Backup complete. Files stored in $BACKUP_ROOT"

exit 0
