
import argparse
import sys
from pathlib import Path

# Allow importing the existing ingestion runner.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_ingestion import run_ingestion


def run_batch(symbols: list[str], intervals: list[str]) -> bool:
    succeeded = 0
    failed = []

    total = len(symbols) * len(intervals)

    for symbol in symbols:
        for interval in intervals:
            print(f"\n[{succeeded + len(failed) + 1}/{total}] "
                  f"{symbol} {interval}", flush=True)

            try:
                run_ingestion(symbol, interval)
                succeeded += 1
            except Exception as exc:
                failed.append((symbol, interval, str(exc)))
                print(f"BATCH ERROR: {symbol} {interval}: {exc}")

    print("\n========== BATCH SUMMARY ==========")
    print(f"Total jobs: {total}")
    print(f"Successful: {succeeded}")
    print(f"Failed: {len(failed)}")

    for symbol, interval, error in failed:
        print(f"FAILED: {symbol} {interval}: {error}")

    return len(failed) == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
    )
    parser.add_argument(
        "--intervals",
        nargs="+",
        default=["1d"],
    )

    args = parser.parse_args()

    symbols = list(dict.fromkeys(
        symbol.upper() for symbol in args.symbols
    ))
    intervals = list(dict.fromkeys(args.intervals))

    success = run_batch(symbols, intervals)
    sys.exit(0 if success else 1)
