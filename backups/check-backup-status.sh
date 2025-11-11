#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT=${BACKUP_DIR:-/backups}
POSTGRES_DIR="$BACKUP_ROOT/postgres"
LATEST=$(ls -1 "$POSTGRES_DIR"/backup-*.dump 2>/dev/null | sort | tail -n1 || true)

if [[ -z "$LATEST" ]]; then
  echo "✗ No backups found in $POSTGRES_DIR"
  exit 1
fi

STAMP=$(basename "$LATEST" .dump)
STAMP=${STAMP#backup-}
LAST_TS=$(date -d "${STAMP:0:8} ${STAMP:9:2}:${STAMP:11:2}:${STAMP:13:2}" +%s)
NOW=$(date +%s)
AGE_HOURS=$(( (NOW - LAST_TS) / 3600 ))

echo "Last backup: $STAMP (${AGE_HOURS}h ago)"
if [[ $AGE_HOURS -gt 30 ]]; then
  echo "✗ Backup is stale (>30h)"
  exit 1
fi

echo "✓ Backup recency OK"
