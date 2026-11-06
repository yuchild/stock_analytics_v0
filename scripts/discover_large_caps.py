
import argparse
from pathlib import Path

import pandas as pd

CANDIDATES = Path("data/processed/us_equity_candidates.csv")
METADATA = Path("data/processed/stock_metadata.csv")
OUTPUT = Path("data/processed/large_cap_discovery.csv")


def normalize_symbol(symbol):
    return str(symbol).strip().upper().replace(".", "-")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-file", required=True)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be positive")

    reference = pd.read_csv(args.reference_file)
    candidates = pd.read_csv(CANDIDATES)
    metadata = pd.read_csv(METADATA)

    required = {"symbol", "market_cap"}

    if not required.issubset(reference.columns):
        raise ValueError(
            f"Reference file requires columns: {required}"
        )

    reference["normalized_symbol"] = (
        reference["symbol"].map(normalize_symbol)
    )

    candidates["normalized_symbol"] = (
        candidates["symbol"].map(normalize_symbol)
    )

    metadata["normalized_symbol"] = (
        metadata["symbol"].map(normalize_symbol)
    )

    reference["market_cap"] = pd.to_numeric(
        reference["market_cap"],
        errors="coerce",
    )

    reference = reference.dropna(
        subset=["market_cap", "normalized_symbol"]
    )

    reference = reference[
        reference["market_cap"] > 0
    ]

    reference = reference.sort_values(
        "market_cap", ascending=False
    ).drop_duplicates("normalized_symbol")

    eligible_symbols = set(
        candidates["normalized_symbol"]
    )

    enriched_symbols = set(
        metadata["normalized_symbol"]
    )

    # Identify reference symbols absent from the filtered universe.
    unmatched = reference[
        ~reference["normalized_symbol"].isin(eligible_symbols)
    ].copy()

    unmatched_path = Path(
        "data/processed/unmatched_large_cap_symbols.csv"
    )

    unmatched_path.parent.mkdir(parents=True, exist_ok=True)

    unmatched.to_csv(unmatched_path, index=False)

    print(f"Unmatched reference symbols: {len(unmatched):,}")
    print(f"Unmatched report: {unmatched_path}")

    missing = reference[
        reference["normalized_symbol"].isin(eligible_symbols)
        & ~reference["normalized_symbol"].isin(enriched_symbols)
    ].copy()

    # Use the exchange-listed symbol for compatibility
    # with enrich_priority_stocks.py.
    symbol_map = dict(
        zip(
            candidates["normalized_symbol"],
            candidates["symbol"],
        )
    )

    missing["symbol"] = missing[
        "normalized_symbol"
    ].map(symbol_map)

    missing = missing.head(args.limit)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    output_columns = ["symbol", "market_cap"]

    if "expected_sector" in missing.columns:
        output_columns.append("expected_sector")

    missing[output_columns].to_csv(
        OUTPUT, index=False
    )

    print(f"Reference companies: {len(reference):,}")
    print(f"Missing candidates: {len(missing):,}")
    print(f"Saved: {OUTPUT}")

    print(
        missing[output_columns]
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
