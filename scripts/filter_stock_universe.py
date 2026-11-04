
from pathlib import Path
import re

import pandas as pd


INPUT = Path("data/external/us_stock_candidates.csv")
OUTPUT = Path("data/processed/us_equity_candidates.csv")
EXCLUDED = Path("data/processed/excluded_candidates.csv")

# Security descriptions indicating non-common-equity instruments.
EXCLUDE_PATTERNS = [
    r"\bwarrants?\b",
    r"\bunits?,?\s+each\s+consisting\b",
    r"\bdepositary shares representing preferred\b",
    r"\bpreferred (?:stock|shares)\b",
    r"\bpreference shares?\b",
    r"\bexchange traded (?:fund|note|product)\b",
    r"\bclosed.end fund\b",
    r"\brights? to (?:purchase|receive)\b",
    r"\bcontingent value rights?\b",
    r"\bsubscription rights?\b",
]

pattern = re.compile(
    "|".join(EXCLUDE_PATTERNS),
    flags=re.IGNORECASE,
)


def main():
    df = pd.read_csv(INPUT, dtype=str).fillna("")

    descriptions = df["security_name"].str.strip()
    excluded_by_name = descriptions.str.contains(
        pattern, regex=True
    )

    # Exclude explicit unit/warrant ticker suffixes.
    # Avoid broad suffix rules that could remove common shares.
    excluded_by_symbol = df["symbol"].str.contains(
        r"\.(?:U|W|WS)$",
        case=False,
        regex=True,
    )

    # Nasdaq commonly uses trailing U, W, WS, or R
    # for units, warrants, and rights.
    # Only exclude these when the security description
    # also identifies the corresponding instrument.
    excluded_by_type = descriptions.str.contains(
        r"\b(?:units?|warrants?|rights?)\b",
        case=False,
        regex=True,
    )

    excluded_by_symbol = excluded_by_symbol | excluded_by_type

    df["exclusion_reason"] = ""
    df.loc[excluded_by_name, "exclusion_reason"] = (
        "Security description"
    )
    df.loc[
        excluded_by_symbol & ~excluded_by_name,
        "exclusion_reason",
    ] = "Ticker suffix"

    excluded = df[
        excluded_by_name | excluded_by_symbol
    ].copy()

    retained = df[
        ~(excluded_by_name | excluded_by_symbol)
    ][["symbol", "security_name"]].copy()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    retained.to_csv(OUTPUT, index=False)
    excluded.to_csv(EXCLUDED, index=False)

    print(f"Original candidates: {len(df):,}")
    print(f"Retained candidates: {len(retained):,}")
    print(f"Excluded candidates: {len(excluded):,}")
    print(f"Saved retained: {OUTPUT}")
    print(f"Saved excluded: {EXCLUDED}")


if __name__ == "__main__":
    main()
