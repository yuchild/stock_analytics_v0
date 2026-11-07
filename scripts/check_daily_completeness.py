#!/usr/bin/env python3
"""Check daily price coverage for the 220-stock universe."""

import argparse
import sys
from datetime import date

from sqlalchemy import text

from stock_analytics.db.connection import engine

import pandas as pd
import exchange_calendars as xcals


def check_completeness(session_date: date) -> list[str]:
    query = text("""
        SELECT DISTINCT u.symbol
        FROM mart.v_sector_top20_candidates_v2 AS u
        WHERE NOT EXISTS (
            SELECT 1
            FROM raw.stock_prices AS p
            WHERE p.symbol = u.symbol
              AND p.interval_code = '1d'
              AND (p.bar_timestamp AT TIME ZONE 'UTC')::date
                  = :session_date
        )
        ORDER BY u.symbol
    """)

    with engine.connect() as connection:
        missing = connection.execute(
            query, {"session_date": session_date}
        ).scalars().all()

    return missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        required=True,
        help="Expected trading session (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    calendar = xcals.get_calendar("XNYS")
    session = pd.Timestamp(args.date)

    if not calendar.is_session(session):
        print(f"SKIP: {args.date} is not an NYSE trading session")
        sys.exit(0)

    missing = check_completeness(args.date)
    total = 220

    print(f"Trading session: {args.date}")
    print(f"Stocks covered: {total - len(missing)}/{total}")
    print(f"Missing stocks: {len(missing)}")

    if missing:
        print("Missing symbols:", " ".join(missing))
        sys.exit(1)

    print("PASS: Daily price coverage complete")


if __name__ == "__main__":
    main()
