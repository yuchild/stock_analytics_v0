#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

# Shared lock across scheduled ingestion workloads.
# Wait up to two hours if another ingestion job is running.
exec 9>"$LOG_DIR/stock_ingestion.lock"

if ! flock -w 7200 9; then
    echo "Could not acquire ingestion lock within 2 hours."
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
        --delay 2 \
        --run-type scheduled \
        --pipeline-name yfinance_ingestion

    echo "Nightly ingestion finished: $(date -Is)"
} > "$LOG_FILE" 2>&1
