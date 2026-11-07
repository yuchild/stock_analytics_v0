#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

LOG_FILE="$LOG_DIR/health_$(TZ=America/Los_Angeles date +%Y%m%d_%H%M%S).log"
SESSION_DATE="$(TZ=America/Los_Angeles date +%F)"

exec > "$LOG_FILE" 2>&1

trap 'status=$?; echo "Health check exit status: $status"' EXIT

echo "Health check started: $(date -Is)"

# Avoid checking the database while ingestion or recovery is running.
exec 9>"$LOG_DIR/nightly_ingestion.lock"

if ! flock -w 300 9; then
    echo "CRITICAL: Could not acquire ingestion lock within 5 minutes."
    exit 2
fi

PYTHONPATH="$PROJECT_DIR/src" \
    "$PROJECT_DIR/.venv/bin/python" \
    "$PROJECT_DIR/scripts/check_pipeline_health.py" \
    --date "$SESSION_DATE"

echo "Health check finished: $(date -Is)"
