
import argparse
import csv
import random
import time
from pathlib import Path

import pandas as pd

from stock_analytics.ingestion.company_metadata import (
    fetch_company_metadata,
)


INPUT = Path("data/processed/us_equity_candidates.csv")
OUTPUT = Path("data/processed/stock_metadata.csv")
FAILURES = Path("data/processed/metadata_failures.csv")

METADATA_FIELDS = [
    "symbol",
    "company_name",
    "sector_name",
    "market_cap",
]

FAILURE_FIELDS = [
    "symbol",
    "error_message",
]


def append_record(path: Path, record: dict, fields: list[str]):
    """Append one record, creating the CSV header if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)

        if file.tell() == 0:
            writer.writeheader()

        writer.writerow(record)


def load_processed_symbols() -> set[str]:
    """Return symbols already successfully enriched."""
    if not OUTPUT.exists():
        return set()

    df = pd.read_csv(OUTPUT, dtype={"symbol": str})
    return set(df["symbol"].dropna().str.upper())


def load_failed_symbols() -> set[str]:
    """Return symbols with recorded failed attempts."""
    if not FAILURES.exists():
        return set()

    df = pd.read_csv(FAILURES, dtype={"symbol": str})
    return set(df["symbol"].dropna().str.upper())


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--delay", type=float, default=2.0)

    args = parser.parse_args()

    if args.limit < 1 or args.delay < 0:
        parser.error("--limit must be >= 1 and --delay must be >= 0")

    candidates = pd.read_csv(INPUT, dtype={"symbol": str})
    processed = load_processed_symbols()
    failed = load_failed_symbols()

    # Exclude previous failures from the normal enrichment pass.
    # We'll build a separate retry mechanism later.
    completed = processed | failed

    remaining = candidates[
        ~candidates["symbol"].str.upper().isin(completed)
    ].head(args.limit)

    print(f"Total candidates: {len(candidates):,}")
    print(f"Previously successful: {len(processed):,}")
    print(f"Processing this run: {len(remaining):,}")

    successes = 0
    failures = 0

    for index, symbol in enumerate(remaining["symbol"], start=1):
        print(f"[{index}/{len(remaining)}] {symbol}", flush=True)

        try:
            metadata = fetch_company_metadata(symbol)

            append_record(OUTPUT, metadata, METADATA_FIELDS)

            successes += 1

            print(
                f"  SUCCESS: {metadata['sector_name']} | "
                f"${metadata['market_cap']:,}"
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
            print(f"  FAILED: {exc}")

        if index < len(remaining):
            time.sleep(args.delay + random.uniform(0, 0.5))

    print("\n========== ENRICHMENT SUMMARY ==========")
    print(f"Successful: {successes}")
    print(f"Failed: {failures}")
    print(f"Previously successful: {len(processed)}")


if __name__ == "__main__":
    main()
