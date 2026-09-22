#!/usr/bin/env bash
set -euo pipefail

# restore.sh — Restore a PostgreSQL dump into the running container.
#
# Usage: ./restore.sh <path-to-dump.sql>
#
# This drops and recreates the records table contents from the dump.

CONTAINER="postgres"
DB_USER="barq_app"
DB_NAME="barq_tasks"

DUMP="${1:-}"
if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
    echo "Usage: $0 <path-to-dump.sql>" >&2
    echo "Example: $0 ./backups/barq_20260922T120000Z.sql" >&2
    exit 1
fi

echo "[restore] Checking container is running..."
if ! docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true; then
    echo "[restore] ERROR: container '$CONTAINER' is not running." >&2
    exit 1
fi

echo "[restore] Piping $DUMP into $CONTAINER..."
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" < "$DUMP"

echo "[restore] Verifying records table..."
COUNT=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM records;" | tr -d '[:space:]')
echo "[restore] OK — records table has $COUNT rows."