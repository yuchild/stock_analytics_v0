#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

# Share the ingestion lock to prevent overlapping jobs.
exec 9>"$LOG_DIR/nightly_ingestion.lock"

if ! flock -n 9; then
    echo "Another ingestion or recovery process is running."
    exit 1
fi

LOG_FILE="$LOG_DIR/recovery_$(date +%Y%m%d_%H%M%S).log"

trap 'status=$?; echo "Recovery exit status: $status" >> "$LOG_FILE"' EXIT

{
    echo "Recovery started: $(date -Is)"

    SESSION_DATE=$(TZ=America/Los_Angeles date +%F)

    echo "Checking trading session: $SESSION_DATE"

    PYTHONPATH="$PROJECT_DIR/src" \
        "$PROJECT_DIR/.venv/bin/python" \
        "$PROJECT_DIR/scripts/recover_daily_prices.py" \
        --date "$SESSION_DATE" \
        --attempts 2 \
        --delay 2

    echo "Recovery finished: $(date -Is)"
} > "$LOG_FILE" 2>&1
