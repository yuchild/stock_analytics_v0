
import argparse
import sys
from pathlib import Path

from sqlalchemy import text
from stock_analytics.db.connection import engine
from stock_analytics.ingestion.yfinance_client import INTERVAL_PERIODS
from stock_analytics.ingestion.batch_logger import (
    start_batch,
    finish_batch,
)

import time

# Allow importing the existing ingestion runner.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_ingestion import run_ingestion


def completed_backfill_exists(symbol: str, interval: str) -> bool:
    query = text("""
        SELECT EXISTS (
            SELECT 1
            FROM analytics.ingestion_log
            WHERE pipeline_name = 'yfinance_ingestion'
              AND symbol = :symbol
              AND interval_code = :interval
              AND ingestion_mode = 'backfill'
              AND requested_period = :period
              AND status = 'success'
        )
    """)

    with engine.connect() as connection:
        return bool(connection.execute(
            query,
            {
                "symbol": symbol,
                "interval": interval,
                "period": INTERVAL_PERIODS[interval],
            },
        ).scalar())


def run_batch(
        symbols: list[str],
        intervals: list[str],
        backfill: bool = False,
        delay: float = 0.0,
        skip_completed: bool = False,
        limit: int | None = None,
        run_type: str = "manual",
    ) -> bool:
    succeeded = 0
    failed = []
    skipped = 0

    total = len(symbols) * len(intervals)

    batch_id = start_batch(
        pipeline_name="yfinance_ingestion",
        run_type=run_type,
        expected_jobs=total,
    )

    print(f"\nStarted batch run: {batch_id}", flush=True)

    try:
        for symbol in symbols:
            if limit is not None and succeeded + len(failed) >= limit:
                print(f"\nBatch limit reached: {limit} attempted jobs")
                break

            for interval in intervals:
                job_number = succeeded + len(failed) + skipped + 1

                print(
                    f"\n[{job_number}/{total}] {symbol} {interval}",
                    flush=True,
                )

                if skip_completed and completed_backfill_exists(symbol, interval):
                    skipped += 1
                    print(f"SKIPPED: {symbol} {interval} (backfill completed)")
                    continue

                try:
                    run_ingestion(symbol, interval, backfill=backfill)
                    succeeded += 1
                except Exception as exc:
                    failed.append((symbol, interval, str(exc)))
                    print(f"BATCH ERROR: {symbol} {interval}: {exc}")
                finally:
                    if delay > 0 and (
                        succeeded + len(failed) + skipped < total
                    ):
                        time.sleep(delay)

                if limit is not None and succeeded + len(failed) >= limit:
                    break

    except BaseException as exc:
        processed = succeeded + len(failed) + skipped

        finish_batch(
            batch_run_id=batch_id,
            status="partial_failure" if processed > 0 else "failed",
            successful_jobs=succeeded,
            failed_jobs=len(failed),
            skipped_jobs=skipped,
            error_message=(
                f"Unexpected interruption: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

        print(
            f"Batch run {batch_id} interrupted: {exc}",
            flush=True,
        )
        raise

    processed = succeeded + len(failed) + skipped
    remaining = total - processed

    print("\n========== BATCH SUMMARY ==========")
    print(f"Total requested jobs: {total}")
    print(f"Successful: {succeeded}")
    print(f"Failed: {len(failed)}")
    print(f"Skipped: {skipped}")
    print(f"Not processed: {remaining}")

    for symbol, interval, error in failed:
        print(f"FAILED: {symbol} {interval}: {error}")

    if remaining == 0 and not failed:
        status = "success"
    elif succeeded > 0 or skipped > 0:
        status = "partial_failure"
    else:
        status = "failed"

    error_details = [
        f"{symbol} {interval}: {error}"
        for symbol, interval, error in failed
    ]

    if remaining > 0:
        error_details.append(f"{remaining} jobs not processed")

    finish_batch(
        batch_run_id=batch_id,
        status=status,
        successful_jobs=succeeded,
        failed_jobs=len(failed),
        skipped_jobs=skipped,
        error_message="\n".join(error_details) or None,
    )

    print(f"Batch run {batch_id} finalized: {status}")

    return status == "success"


def load_top20_symbols() -> list[str]:
    """Load the current top-20 stocks from all 11 sectors."""

    query = text("""
        SELECT DISTINCT symbol
        FROM mart.v_sector_top20_candidates_v2
        ORDER BY symbol
    """)

    with engine.connect() as connection:
        symbols = connection.execute(query).scalars().all()

    if len(symbols) != 220:
        raise ValueError(
            f"Expected 220 unique symbols, found {len(symbols)}"
        )

    print(f"Loaded {len(symbols)} top-20 symbols from PostgreSQL")

    return symbols


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--symbols",
        nargs="+",
    )
    parser.add_argument(
        "--top20",
        action="store_true",
        help="Load all 220 top-sector stocks from PostgreSQL",
    )
    parser.add_argument(
        "--intervals",
        nargs="+",
        default=["1d"],
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Download full configured history for each symbol",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds to wait between ingestion jobs",
    )
    parser.add_argument(
        "--skip-completed",
        action="store_true",
        help="Skip previously successful backfills for the same period",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of unfinished ingestion jobs to run",
    )
    parser.add_argument(
        "--run-type",
        choices=["manual", "scheduled"],
        default="manual",
        help="Identify whether the batch was launched manually or by cron",
    )

    args = parser.parse_args()

    if args.top20 and args.symbols:
        parser.error("Use either --top20 or --symbols, not both")

    if not args.top20 and not args.symbols:
        parser.error("Provide --symbols or --top20")

    if args.top20:
        symbols = load_top20_symbols()
    else:
        symbols = list(dict.fromkeys(
            symbol.upper() for symbol in args.symbols
        ))

    if args.skip_completed and not args.backfill:
        parser.error("--skip-completed requires --backfill")

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")

    intervals = list(dict.fromkeys(args.intervals))

    success = run_batch(
        symbols,
        intervals,
        backfill=args.backfill,
        delay=args.delay,
        skip_completed=args.skip_completed,
        limit=args.limit,
        run_type=args.run_type,
    )

    sys.exit(0 if success else 1)
