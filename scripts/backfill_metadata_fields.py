
import argparse
import random
import time
from pathlib import Path

import pandas as pd

from stock_analytics.ingestion.company_metadata import (
    fetch_company_metadata,
)

SOURCE = Path("data/processed/stock_metadata.csv")
FAILURES = Path("data/processed/metadata_backfill_failures.csv")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=5,
    )
    args = parser.parse_args()

    if (
        args.limit < 1
        or args.delay < 0
        or args.max_consecutive_failures < 1
    ):
        parser.error("Invalid batch parameters")

    df = pd.read_csv(SOURCE, dtype={"symbol": str})

    if df["symbol"].duplicated().any():
        raise ValueError("Duplicate metadata symbols")

    missing = df[
        df["quote_type"].isna()
        | df["industry_name"].isna()
    ]

    symbols = missing["symbol"].head(args.limit).tolist()

    print("Records requiring backfill:", len(missing))
    print("Processing:", len(symbols))

    successes = 0
    failures = 0
    consecutive_failures = 0

    for index, symbol in enumerate(symbols, start=1):
        print(f"[{index}/{len(symbols)}] {symbol}", flush=True)

        try:
            metadata = fetch_company_metadata(symbol)

            mask = df["symbol"] == symbol

            updated = []

            for field in ["quote_type", "industry_name"]:
                value = metadata.get(field)

                if (
                    pd.notna(value)
                    and str(value).strip()
                    and df.loc[mask, field].isna().all()
                ):
                    df.loc[mask, field] = value
                    updated.append(field)

            if not updated:
                raise ValueError(
                    "Yahoo returned no usable missing fields"
                )

            # Save after every successful symbol so progress
            # survives interruption.
            temp = SOURCE.with_suffix(".tmp")
            df.to_csv(temp, index=False)
            temp.replace(SOURCE)

            successes += 1
            consecutive_failures = 0
            print("  UPDATED:", ", ".join(updated))

        except Exception as exc:
            failures += 1
            consecutive_failures += 1
            print("  FAILED:", exc)

            record = pd.DataFrame([{
                "symbol": symbol,
                "error_message": str(exc),
            }])

            record.to_csv(
                FAILURES,
                mode="a",
                header=not FAILURES.exists(),
                index=False,
            )
            
            if consecutive_failures >= args.max_consecutive_failures:
                print("STOPPING: Maximum consecutive failures reached.")
                break

        if index < len(symbols):
            time.sleep(args.delay + random.uniform(0, 0.5))

    print("\n========== BACKFILL SUMMARY ==========")
    print("Successful:", successes)
    print("Failed:", failures)


if __name__ == "__main__":
    main()
