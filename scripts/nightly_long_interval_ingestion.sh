
#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

INTERVAL="${1:-}"

case "$INTERVAL" in
    1wk)
        PIPELINE_NAME="yfinance_weekly"
        LOG_PREFIX="weekly"
        ;;
    1mo)
        PIPELINE_NAME="yfinance_monthly"
        LOG_PREFIX="monthly"
        ;;
    *)
        echo "Usage: $0 {1wk|1mo}" >&2
        exit 2
        ;;
esac

# Coordinate with intraday, daily, and recovery workloads.
exec 9>"$LOG_DIR/stock_ingestion.lock"

if ! flock -w 7200 9; then
    echo "Could not acquire ingestion lock within 2 hours." >&2
    exit 1
fi

LOG_FILE="$LOG_DIR/${LOG_PREFIX}_$(date +%Y%m%d_%H%M%S).log"

trap 'status=$?; echo "Ingestion exit status: $status" >> "$LOG_FILE"' EXIT

{
    echo "$PIPELINE_NAME started: $(date -Is)"

    PYTHONPATH="$PROJECT_DIR/src" \
        "$PROJECT_DIR/.venv/bin/python" \
        "$PROJECT_DIR/scripts/run_batch_ingestion.py" \
        --top20 \
        --intervals "$INTERVAL" \
        --delay 2 \
        --run-type scheduled \
        --pipeline-name "$PIPELINE_NAME"

    echo "$PIPELINE_NAME finished: $(date -Is)"
} > "$LOG_FILE" 2>&1
