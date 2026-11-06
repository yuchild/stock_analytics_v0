
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
    r"\b(?:income|investment|opportunities|credit strategies|convertible) fund\b",
    r"\bclosed[- ]end\b",
    r"\bincome trust\b",
    r"\bpreferred securities\b",
    r"\bsubordinated debentures\b",
    r"\bperpetual (?:conv(?:ertible)? )?pfd\b",
    r"\bpfd ser(?:ies)?\b",
    r"\bdepositary sh(?:ares?)?\s+repstg\b",
    r"\bBlackRock .+ Trust\b",
    r"\b(?:closed[- ]end|closed end) (?:investment )?fund\b",
    
    # Additional preferred securities, funds, and ETNs
    r"\bpreferred class\b",
    r"\bpreferred and income\b",
    r"\bconvertible and income securities fund\b",
    r"\bexchange[- ]traded notes?\b",

    # Debt securities
    r"\bsenior (?:secured |unsecured )?notes?\b",
    r"\bsubordinated notes?\b",
    r"\b(?:fixed|floating)[- ]rate notes?\b",
    r"\bnotes? due \d{4}\b",
    r"\bdebentures?\b",
    r"\bbonds? due \d{4}\b",

    # Preferred and depositary securities
    r"\bpreferred shares?\b",
    r"\bpreferred stock\b",
    r"\bnon[- ]cumulative preferred\b",
    r"\bdepositary receipts? representing preferred\b",
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
        r"\b(?:warrants?|rights?)\b"
        r"|\bunits?,?\s+each\s+consisting\b"
        r"|\b(?:SPAC|blank.check)\s+units?\b",
        case=False,
        regex=True,
    )

    # Exclude generic units unless the description identifies
    # an operating partnership ownership interest.
    unit_description = descriptions.str.contains(
        r"\bunits?\b",
        case=False,
        regex=True,
    )

    partnership_ownership = descriptions.str.contains(
        r"\b(?:common|limited partnership|partnership)\s+units?\b"
        r"|\bunits?\s+representing\s+limited partner\b"
        r"|\blimited partnership interests?\b"
        r"|\bholding\s+l\.p\.\s+units?\b",
        case=False,
        regex=True,
    )

    generic_units = unit_description & ~partnership_ownership

    # Preferred units remain excluded regardless of ownership wording.
    preferred_units = descriptions.str.contains(
        r"\b(?:preferred|preference|cumulative redeemable)\b"
        r".*\bunits?\b",
        case=False,
        regex=True,
    )

    excluded_by_symbol = (
        excluded_by_symbol
        | excluded_by_type
        | generic_units
        | preferred_units
    )

    # Dollar-sign ticker suffixes commonly identify preferred
    # shares or other non-common-equity instruments.
    excluded_by_symbol = (
        excluded_by_symbol
        | df["symbol"].str.contains(r"\$", regex=True)
    )

    generic_depositary = descriptions.str.contains(
        r"\bdepositary shares?\b",
        case=False,
        regex=True,
    ) & ~descriptions.str.contains(
        r"\bamerican depositary shares?\b",
        case=False,
        regex=True,
    )

    excluded_by_name = excluded_by_name | generic_depositary

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
