#!/usr/bin/env bash
set -euo pipefail

# backup.sh — Dump the PostgreSQL database from the running container.
# Writes to ./backups/barq_<timestamp>.sql
#
# Usage: ./backup.sh [output-dir]

CONTAINER="postgres"
DB_USER="barq_app"
DB_NAME="barq_tasks"

OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${OUT_DIR}/barq_${STAMP}.sql"

echo "[backup] Checking container is running..."
if ! docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true; then
    echo "[backup] ERROR: container '$CONTAINER' is not running." >&2
    exit 1
fi

echo "[backup] Dumping $DB_NAME from $CONTAINER to $OUT_FILE..."
docker exec "$CONTAINER" pg_dump -U "$DB_USER" --clean --if-exists "$DB_NAME" > "$OUT_FILE"

if [ ! -s "$OUT_FILE" ]; then
    echo "[backup] ERROR: dump file is empty." >&2
    exit 1
fi

LINES=$(wc -l < "$OUT_FILE")
SIZE=$(du -h "$OUT_FILE" | cut -f1)
echo "[backup] OK — $OUT_FILE ($LINES lines, $SIZE)"