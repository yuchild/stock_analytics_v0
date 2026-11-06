#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

exec 9>"$LOG_DIR/nightly_ingestion.lock"

if ! flock -n 9; then
    echo "Another ingestion process is already running."
    exit 1
fi

LOG_FILE="$LOG_DIR/nightly_$(date +%Y%m%d_%H%M%S).log"

trap 'status=$?; echo "Nightly ingestion exit status: $status" >> "$LOG_FILE"' EXIT

{
    echo "Nightly ingestion started: $(date -Is)"

    PYTHONPATH="$PROJECT_DIR/src" \
        "$PROJECT_DIR/.venv/bin/python" \
        "$PROJECT_DIR/scripts/run_batch_ingestion.py" \
        --top20 \
        --intervals 1d \
        --delay 2

    echo "Nightly ingestion finished: $(date -Is)"
} > "$LOG_FILE" 2>&1
