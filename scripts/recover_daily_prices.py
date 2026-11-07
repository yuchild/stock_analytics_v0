#!/usr/bin/env python3
"""Recover missing daily bars for a specified NYSE trading session."""

import argparse
import sys
import time
from datetime import date

import exchange_calendars as xcals
import pandas as pd

from check_daily_completeness import check_completeness
from run_ingestion import run_ingestion


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()

    if args.attempts < 1 or args.delay < 0:
        parser.error("--attempts must be >= 1 and --delay >= 0")

    calendar = xcals.get_calendar("XNYS")

    if not calendar.is_session(pd.Timestamp(args.date)):
        print(f"SKIP: {args.date} is not an NYSE trading session")
        return 0

    for attempt in range(1, args.attempts + 1):
        missing = check_completeness(args.date)

        if not missing:
            print(f"PASS: All 220 stocks complete for {args.date}")
            return 0

        print(
            f"Recovery attempt {attempt}/{args.attempts}: "
            f"{len(missing)} missing stocks",
            flush=True,
        )

        for symbol in missing:
            try:
                run_ingestion(symbol, "1d", backfill=False)
            except Exception as exc:
                print(f"RECOVERY ERROR: {symbol}: {exc}", flush=True)

            if args.delay:
                time.sleep(args.delay)

    remaining = check_completeness(args.date)

    if remaining:
        print(f"FAIL: {len(remaining)} stocks remain missing")
        print("Missing symbols:", " ".join(remaining))
        return 1

    print(f"PASS: All 220 stocks complete for {args.date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
