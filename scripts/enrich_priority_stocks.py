
import argparse
import random
import time

import pandas as pd

from enrich_stock_universe import (
    INPUT,
    OUTPUT,
    FAILURES,
    METADATA_FIELDS,
    FAILURE_FIELDS,
    append_record,
    load_processed_symbols,
    load_failed_symbols,
)
from stock_analytics.ingestion.company_metadata import (
    fetch_company_metadata,
)

PRIORITY_FILE = "data/external/large_cap_priority.csv"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--priority-file",
        default="data/external/large_cap_priority.csv",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry symbols previously recorded in the failure log.",
    )
    args = parser.parse_args()

    if (
        args.limit < 1
        or args.delay < 0
        or args.max_consecutive_failures < 1
    ):
        parser.error("Invalid batch parameters")

    priority = pd.read_csv(
        args.priority_file,
        dtype={"symbol": str},
    )

    candidates = set(
        pd.read_csv(INPUT, dtype={"symbol": str})["symbol"]
    )

    processed = load_processed_symbols()
    failed = load_failed_symbols()

    if priority["symbol"].duplicated().any():
        raise ValueError("Duplicate priority symbols")

    print(
        "Previously failed in priority batch:",
        len(set(priority["symbol"]) & failed),
    )
    print("Retry failed enabled:", args.retry_failed)

    remaining = [
        symbol
        for symbol in priority["symbol"]
        if symbol in candidates
        and symbol not in processed
        and (args.retry_failed or symbol not in failed)
    ][:args.limit]

    print(f"Priority stocks: {len(priority)}")
    print(
        "Already enriched:",
        len(set(priority.symbol) & processed),
    )
    print(f"Processing this run: {len(remaining)}")

    successes = 0
    failures = 0
    consecutive_failures = 0

    for index, symbol in enumerate(remaining, start=1):
        print(f"[{index}/{len(remaining)}] {symbol}", flush=True)

        try:
            metadata = fetch_company_metadata(symbol)

            append_record(
                OUTPUT,
                metadata,
                METADATA_FIELDS,
            )

            successes += 1
            consecutive_failures = 0

            print(
                f"  SUCCESS: {metadata['sector_name']} "
                f"| ${metadata['market_cap']:,}"
            )

        except Exception as exc:
            append_record(
                FAILURES,
                {
                    "symbol": symbol,
                    "error_message": str(exc),
                },
                FAILURE_FIELDS,
            )

            failures += 1
            consecutive_failures += 1

            print(f"  FAILED: {exc}")

            if (
                consecutive_failures
                >= args.max_consecutive_failures
            ):
                print(
                    "STOPPING: Maximum consecutive "
                    "failures reached."
                )
                break

        if index < len(remaining):
            time.sleep(
                args.delay + random.uniform(0, 0.5)
            )

    print("\n========== PRIORITY SUMMARY ==========")
    print(f"Successful: {successes}")
    print(f"Failed: {failures}")


if __name__ == "__main__":
    main()
