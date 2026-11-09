
#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

SESSION_DATE="$(TZ=America/Los_Angeles date +%F)"
LOG_FILE="$LOG_DIR/workload_health_$(TZ=America/Los_Angeles date +%Y%m%d_%H%M%S).log"

exec > "$LOG_FILE" 2>&1

trap 'status=$?; echo "Workload health check exit status: $status"' EXIT

echo "Workload health check started: $(date -Is)"
echo "Trading session: $SESSION_DATE"

# Wait until ingestion and recovery workloads have completed.
exec 9>"$LOG_DIR/stock_ingestion.lock"

if ! flock -w 7200 9; then
    echo "CRITICAL: Could not acquire ingestion lock within 2 hours."
    exit 2
fi

PYTHONPATH="$PROJECT_DIR/src" \
    "$PROJECT_DIR/.venv/bin/python" \
    "$PROJECT_DIR/scripts/check_scheduled_workloads.py" \
    --date "$SESSION_DATE"

echo "Workload health check finished: $(date -Is)"
