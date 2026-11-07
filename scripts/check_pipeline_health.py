#!/usr/bin/env python3
"""Monitor nightly stock ingestion and daily price completeness."""

import argparse
import sys
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd
from sqlalchemy import text

from check_daily_completeness import check_completeness
from stock_analytics.db.connection import engine


PACIFIC = ZoneInfo("America/Los_Angeles")


def check_pipeline(
    session_date: date,
    simulate_missing: bool = False,
    simulate_failed_job: bool = False,
) -> int:
    calendar = xcals.get_calendar("XNYS")

    if not calendar.is_session(pd.Timestamp(session_date)):
        print(f"SKIP: {session_date} is not an NYSE trading session")
        return 0

    window_start = datetime.combine(
        session_date, time(18, 0), tzinfo=PACIFIC
    )
    window_end = datetime.combine(
        session_date, time(19, 0), tzinfo=PACIFIC
    )

    query = text("""
        SELECT
            COUNT(*) AS total_jobs,
            COUNT(DISTINCT symbol) AS distinct_symbols,
            COUNT(*) FILTER (
                WHERE status = 'success'
            ) AS successful_jobs,
            COUNT(*) FILTER (
                WHERE status <> 'success'
                   OR status IS NULL
            ) AS failed_jobs
        FROM analytics.ingestion_log
        WHERE pipeline_name = 'yfinance_ingestion'
          AND interval_code = '1d'
          AND ingestion_mode = 'incremental'
          AND started_at >= :window_start
          AND started_at < :window_end
    """)

    with engine.connect() as connection:
        result = connection.execute(
            query,
            {
                "window_start": window_start,
                "window_end": window_end,
            },
        ).mappings().one()

    missing = check_completeness(session_date)

    # Optional test mode: simulate missing data without changing PostgreSQL.
    if simulate_missing:
        missing = sorted(set(missing) | {"AAPL"})

    total_jobs = result["total_jobs"]
    successful = result["successful_jobs"]
    failed = result["failed_jobs"]
    distinct = result["distinct_symbols"]

    if simulate_failed_job:
        failed += 1
        successful = max(0, successful - 1)

    print("\n========== PIPELINE HEALTH ==========")
    print(f"Trading session: {session_date}")
    print(f"Primary ingestion jobs: {total_jobs}")
    print(f"Successful jobs: {successful}")
    print(f"Failed jobs: {failed}")
    print(f"Distinct symbols processed: {distinct}/220")
    print(f"Daily price coverage: {220 - len(missing)}/220")

    if missing:
        print("Missing symbols:", " ".join(missing))

    execution_healthy = (
        total_jobs == 220
        and successful == 220
        and failed == 0
        and distinct == 220
    )

    data_healthy = len(missing) == 0

    if execution_healthy and data_healthy:
        print("STATUS: HEALTHY")
        return 0

    if data_healthy:
        print("STATUS: DEGRADED — data complete, execution issues")
        return 1

    print("STATUS: CRITICAL — incomplete daily prices")
    return 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=datetime.now(PACIFIC).date(),
    )
    parser.add_argument("--simulate-missing", action="store_true")
    parser.add_argument("--simulate-failed-job", action="store_true")
    
    args = parser.parse_args()

    return check_pipeline(
        args.date,
        simulate_missing=args.simulate_missing,
        simulate_failed_job=args.simulate_failed_job,
    )


if __name__ == "__main__":
    sys.exit(main())