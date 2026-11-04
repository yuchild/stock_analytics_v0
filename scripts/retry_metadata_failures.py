
import argparse
import random
import time

import pandas as pd

from enrich_stock_universe import (
    INPUT,
    OUTPUT,
    FAILURES,
    METADATA_FIELDS,
    append_record,
)
from stock_analytics.ingestion.company_metadata import (
    fetch_company_metadata,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--delay", type=float, default=3.0)
    args = parser.parse_args()

    if args.limit < 1 or args.delay < 0:
        parser.error("--limit must be >= 1 and --delay must be >= 0")

    if not FAILURES.exists():
        print("No failure checkpoint found.")
        return

    failures = pd.read_csv(FAILURES, dtype=str)
    candidates = set(pd.read_csv(INPUT, dtype=str)["symbol"])

    successful = set()
    if OUTPUT.exists():
        successful = set(
            pd.read_csv(OUTPUT, dtype=str)["symbol"]
        )

    # Retry only current candidates without successful metadata.
    retry_symbols = [
        symbol
        for symbol in failures["symbol"].dropna().unique()
        if symbol in candidates and symbol not in successful
    ][:args.limit]

    print(f"Eligible failed symbols: {len(retry_symbols)}")

    for index, symbol in enumerate(retry_symbols, start=1):
        print(f"[{index}/{len(retry_symbols)}] {symbol}")

        try:
            metadata = fetch_company_metadata(symbol)
            append_record(OUTPUT, metadata, METADATA_FIELDS)
            print(f"  RECOVERED: {symbol}")
        except Exception as exc:
            print(f"  STILL FAILED: {symbol}: {exc}")

        if index < len(retry_symbols):
            time.sleep(args.delay + random.uniform(0, 0.5))


if __name__ == "__main__":
    main()
