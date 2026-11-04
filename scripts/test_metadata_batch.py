
import time

import pandas as pd

from stock_analytics.ingestion.company_metadata import (
    fetch_company_metadata,
)


TEST_SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "BRK.B",
    "JPM",
    "JNJ",
    "XOM",
    "WMT",
    "NEE",
]


def main():
    results = []
    failures = []

    for index, symbol in enumerate(TEST_SYMBOLS, start=1):
        print(f"[{index}/{len(TEST_SYMBOLS)}] {symbol}", flush=True)

        try:
            metadata = fetch_company_metadata(symbol)
            results.append(metadata)

            print(
                f"  SUCCESS: {metadata['sector_name']} | "
                f"${metadata['market_cap']:,}"
            )

        except Exception as exc:
            failures.append((symbol, str(exc)))
            print(f"  FAILED: {exc}")

        if index < len(TEST_SYMBOLS):
            time.sleep(2)

    df = pd.DataFrame(results)

    print("\n========== SUMMARY ==========")
    print(f"Successful: {len(results)}")
    print(f"Failed: {len(failures)}")

    if not df.empty:
        print("\nSector distribution:")
        print(df["sector_name"].value_counts().to_string())

    for symbol, error in failures:
        print(f"FAILED: {symbol}: {error}")


if __name__ == "__main__":
    main()
