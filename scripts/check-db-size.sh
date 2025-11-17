#!/usr/bin/env bash
set -euo pipefail

POSTGRES_CONTAINER=${POSTGRES_CONTAINER:-brainda-postgres}
PG_USER=${POSTGRES_USER:-postgres}
PG_DB=${POSTGRES_DB:-vib}

cmd() {
  docker exec "$POSTGRES_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -c "$1"
}

echo "Brainda Database Size Report"
echo "========================"
echo ""
cmd "SELECT pg_size_pretty(pg_database_size('$PG_DB')) AS database_size;"
echo ""
cmd "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 20;"
echo ""
cmd "SELECT 'messages' AS table_name, COUNT(*) AS rows, MIN(created_at) AS oldest, MAX(created_at) AS newest FROM messages
UNION ALL
SELECT 'jobs', COUNT(*), MIN(created_at), MAX(created_at) FROM jobs
UNION ALL
SELECT 'notification_delivery', COUNT(*), MIN(created_at), MAX(created_at) FROM notification_delivery
UNION ALL
SELECT 'audit_log', COUNT(*), MIN(created_at), MAX(created_at) FROM audit_log;"
