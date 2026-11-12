#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
PYTHON="$PROJECT_DIR/.venv/bin/python"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

LOG_FILE="$LOG_DIR/price_quality_$(TZ=America/Los_Angeles date +%Y%m%d_%H%M%S).log"
exec > "$LOG_FILE" 2>&1
trap 'status=$?; echo "Price quality monitor exit status: $status"' EXIT

echo "Price quality monitor started: $(date -Is)"

# Use the latest completed NYSE session, not an uncompleted current-day candle.
# This also handles exchange holidays when the launcher runs on a weekday.
if ! SESSION_DATE="$(TZ=America/Los_Angeles "$PYTHON" - <<'PY'
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import exchange_calendars as xcals
import pandas as pd

calendar = xcals.get_calendar("XNYS")
now = pd.Timestamp(datetime.now(ZoneInfo("America/New_York")))
today = pd.Timestamp(now.date())
session = calendar.date_to_session(today, direction="previous")
if calendar.is_session(today) and now < calendar.session_close(today):
    session = calendar.previous_session(today)
print(session.date().isoformat())
PY
)"; then
    echo "CRITICAL: Could not determine latest completed NYSE session."
    exit 2
fi

echo "Trading session: $SESSION_DATE"
echo "Log file: $LOG_FILE"

# Wait for all ingestion and recovery jobs to finish.
exec 9>"$LOG_DIR/stock_ingestion.lock"
if ! flock -w 7200 9; then
    echo "CRITICAL: Could not acquire ingestion lock within 2 hours."
    exit 2
fi

set +e
PYTHONPATH="$PROJECT_DIR/src" \
    "$PYTHON" \
    "$PROJECT_DIR/scripts/check_price_data_quality.py" \
    --date "$SESSION_DATE"
quality_status=$?
set -e

case "$quality_status" in
    0)
        echo "QUALITY PASS: No findings for $SESSION_DATE."
        ;;
    1)
        echo "QUALITY WARNING: Findings recorded for $SESSION_DATE; ingestion status is unaffected."
        ;;
    *)
        echo "CRITICAL: Price quality validator failed (exit code $quality_status)."
        exit 2
        ;;
esac

echo "Price quality monitor finished: $(date -Is)"
