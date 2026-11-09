
#!/usr/bin/env python3
"""Check scheduled ingestion batches across all seven intervals."""

import argparse
import sys
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd
from sqlalchemy import text

from stock_analytics.db.connection import engine


PACIFIC = ZoneInfo("America/Los_Angeles")

# First date on which the new cron schedule is expected.
TRACKING_START = date(2026, 11, 9)

WORKLOADS = {
    "yfinance_intraday": {
        "intervals": ("1m", "5m", "15m", "1h"),
        "expected_jobs": 880,
        "scheduled_time": time(16, 15),
    },
    "yfinance_ingestion": {
        "intervals": ("1d",),
        "expected_jobs": 220,
        "scheduled_time": time(18, 0),
    },
    "yfinance_weekly": {
        "intervals": ("1wk",),
        "expected_jobs": 220,
        "scheduled_time": time(20, 15),
    },
    "yfinance_monthly": {
        "intervals": ("1mo",),
        "expected_jobs": 220,
        "scheduled_time": time(20, 15),
    },
}


def expected_workloads(session_date: date) -> list[str]:
    """Return workloads scheduled for the given trading session."""

    calendar = xcals.get_calendar("XNYS")

    if not calendar.is_session(pd.Timestamp(session_date)):
        return []

    workloads = [
        "yfinance_intraday",
        "yfinance_ingestion",
    ]

    if session_date.weekday() == 4:
        workloads.append("yfinance_weekly")

    workloads.append("yfinance_monthly")

    return workloads


def check_workloads(
    session_date: date,
    simulate_missing: str | None = None,
) -> int:
    """Check execution records for scheduled ingestion workloads."""

    if session_date < TRACKING_START:
        print(
            f"SKIP: Batch monitoring begins on {TRACKING_START}"
        )
        return 0

    names = expected_workloads(session_date)

    if not names:
        print(
            f"SKIP: {session_date} is not an NYSE trading session"
        )
        return 0

    window_start = datetime.combine(
        session_date,
        time.min,
        tzinfo=PACIFIC,
    )

    window_end = window_start + timedelta(days=1)

    query = text("""
        SELECT
            batch_run_id,
            pipeline_name,
            run_type,
            status,
            expected_jobs,
            successful_jobs,
            failed_jobs,
            skipped_jobs,
            started_at,
            finished_at
        FROM analytics.batch_runs
        WHERE run_type = 'scheduled'
          AND started_at >= :window_start
          AND started_at < :window_end
        ORDER BY started_at, batch_run_id
    """)

    with engine.connect() as connection:
        records = connection.execute(
            query,
            {
                "window_start": window_start,
                "window_end": window_end,
            },
        ).mappings().all()

    batches_by_pipeline = {
        name: [] for name in names
    }

    for record in records:
        pipeline = record["pipeline_name"]

        if pipeline in batches_by_pipeline:
            batches_by_pipeline[pipeline].append(record)

    if simulate_missing in batches_by_pipeline:
        batches_by_pipeline[simulate_missing] = []

    print("\n========== SCHEDULED WORKLOAD HEALTH ==========")
    print(f"Trading session: {session_date}")
    print(f"Workloads expected: {len(names)}")

    problems = []

    for name in names:
        config = WORKLOADS[name]
        batches = batches_by_pipeline[name]
        expected = config["expected_jobs"]

        print(f"\nPipeline: {name}")
        print(
            "Intervals: "
            + ", ".join(config["intervals"])
        )
        print(f"Expected jobs: {expected}")
        print(f"Batches found: {len(batches)}")

        if not batches:
            print("STATUS: MISSING")
            problems.append(f"{name}: no scheduled batch")
            continue

        if len(batches) != 1:
            print("STATUS: DUPLICATE")
            problems.append(
                f"{name}: {len(batches)} scheduled batches"
            )
            continue

        batch = batches[0]

        print(f"Batch ID: {batch['batch_run_id']}")
        print(f"Batch status: {batch['status']}")
        print(f"Successful: {batch['successful_jobs']}")
        print(f"Failed: {batch['failed_jobs']}")
        print(f"Skipped: {batch['skipped_jobs']}")

        healthy = (
            batch["status"] == "success"
            and batch["finished_at"] is not None
            and batch["expected_jobs"] == expected
            and batch["successful_jobs"] == expected
            and batch["failed_jobs"] == 0
            and batch["skipped_jobs"] == 0
        )

        if healthy:
            print("STATUS: HEALTHY")
        else:
            print("STATUS: UNHEALTHY")
            problems.append(
                f"{name}: batch execution incomplete or failed"
            )

    print("\n========== OVERALL RESULT ==========")

    if problems:
        for problem in problems:
            print(f"ISSUE: {problem}")

        print("STATUS: UNHEALTHY")
        return 1

    print("STATUS: HEALTHY")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monitor scheduled stock ingestion workloads"
    )

    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=datetime.now(PACIFIC).date(),
    )

    parser.add_argument(
        "--simulate-missing",
        choices=list(WORKLOADS),
        default=None,
    )

    args = parser.parse_args()

    return check_workloads(
        session_date=args.date,
        simulate_missing=args.simulate_missing,
    )


if __name__ == "__main__":
    sys.exit(main())
