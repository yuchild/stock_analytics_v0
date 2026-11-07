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
BATCH_TRACKING_START = date(2026, 11, 9)


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

    batch_query = text("""
        SELECT
            batch_run_id,
            COUNT(*) OVER () AS batch_count,
            status,
            expected_jobs,
            successful_jobs,
            failed_jobs,
            skipped_jobs,
            started_at,
            finished_at
        FROM analytics.batch_runs
        WHERE pipeline_name = 'yfinance_ingestion'
          AND run_type = 'scheduled'
          AND started_at >= :window_start
          AND started_at < :window_end
        ORDER BY started_at DESC, batch_run_id DESC
        LIMIT 1
    """)

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
        batch_result = connection.execute(
            batch_query,
            {
                "window_start": window_start,
                "window_end": window_end,
            },
        ).mappings().one_or_none()
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
    if batch_result is None:
        print("Scheduled batch: NOT FOUND")
    else:
        print(f"Batch ID: {batch_result['batch_run_id']}")
        print(f"Batch status: {batch_result['status']}")
        print(f"Expected jobs: {batch_result['expected_jobs']}")
        print(f"Batch successful jobs: {batch_result['successful_jobs']}")
        print(f"Batch failed jobs: {batch_result['failed_jobs']}")
        print(f"Batch skipped jobs: {batch_result['skipped_jobs']}")
        print(f"Scheduled batch count: {batch_result['batch_count']}")
    print(f"Trading session: {session_date}")
    print(f"Primary ingestion jobs: {total_jobs}")
    print(f"Successful jobs: {successful}")
    print(f"Failed jobs: {failed}")
    print(f"Distinct symbols processed: {distinct}/220")
    print(f"Daily price coverage: {220 - len(missing)}/220")

    if missing:
        print("Missing symbols:", " ".join(missing))

    legacy_execution_healthy = (
        total_jobs == 220
        and successful == 220
        and failed == 0
        and distinct == 220
    )

    if session_date < BATCH_TRACKING_START:
        execution_healthy = legacy_execution_healthy
    else:
        execution_healthy = (
            batch_result is not None
            and batch_result["batch_count"] == 1
            and batch_result["status"] == "success"
            and batch_result["finished_at"] is not None
            and batch_result["expected_jobs"] == 220
            and batch_result["successful_jobs"] == 220
            and batch_result["failed_jobs"] == 0
            and batch_result["skipped_jobs"] == 0
        )

    data_healthy = len(missing) == 0

    # Simulate an execution failure for both legacy and batch-tracked runs.
    if simulate_failed_job:
        execution_healthy = False

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