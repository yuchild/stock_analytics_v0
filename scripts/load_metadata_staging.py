
import pandas as pd
from sqlalchemy import text

from stock_analytics.db.connection import engine

from stock_analytics.ingestion.security_classification import (
    classify_security,
)

METADATA_PATH = "data/processed/stock_metadata.csv"
CANDIDATES_PATH = "data/processed/us_equity_candidates.csv"
OVERRIDES_PATH = (
    "data/reference/security_classification_overrides.csv"
)


def optional_string(value):
    return None if pd.isna(value) else str(value)


def main():
    metadata = pd.read_csv(
        METADATA_PATH,
        dtype={"symbol": str},
    )

    candidates = pd.read_csv(
        CANDIDATES_PATH,
        dtype={"symbol": str},
    )

    eligible_symbols = set(candidates["symbol"])

    metadata["is_eligible"] = (
        metadata["symbol"].isin(eligible_symbols)
    )

    if metadata["symbol"].duplicated().any():
        raise ValueError("Duplicate metadata symbols detected")

    overrides_df = pd.read_csv(
        OVERRIDES_PATH,
        dtype={"symbol": str, "security_type": str},
        keep_default_na=False,
    )

    if overrides_df["symbol"].duplicated().any():
        raise ValueError("Duplicate classification overrides")

    overrides = overrides_df.set_index("symbol").to_dict("index")

    for column in ["quote_type", "industry_name"]:
        if column not in metadata.columns:
            metadata[column] = None

    query = text("""
        INSERT INTO staging.company_metadata (
            symbol,
            company_name,
            sector_name,
            market_cap,
            is_eligible,
            quote_type,
            industry_name,
            security_type,
            eligibility_reason,
            fetched_at
        )
        VALUES (
            :symbol,
            :company_name,
            :sector_name,
            :market_cap,
            :is_eligible,
            :quote_type,
            :industry_name,
            :security_type,
            :eligibility_reason,
            NULL
        )
        ON CONFLICT (symbol)
        DO UPDATE SET
            company_name = EXCLUDED.company_name,
            sector_name = EXCLUDED.sector_name,
            market_cap = EXCLUDED.market_cap,
            is_eligible = EXCLUDED.is_eligible,
            quote_type = COALESCE(
                EXCLUDED.quote_type,
                staging.company_metadata.quote_type
            ),
            industry_name = COALESCE(
                EXCLUDED.industry_name,
                staging.company_metadata.industry_name
            ),
            security_type = CASE
                WHEN EXCLUDED.quote_type IS NULL
                AND EXCLUDED.industry_name IS NULL
                THEN COALESCE(
                    staging.company_metadata.security_type,
                    EXCLUDED.security_type
                )
                ELSE EXCLUDED.security_type
            END,
            eligibility_reason = CASE
                WHEN EXCLUDED.quote_type IS NULL
                AND EXCLUDED.industry_name IS NULL
                THEN COALESCE(
                    staging.company_metadata.eligibility_reason,
                    EXCLUDED.eligibility_reason
                )
                ELSE EXCLUDED.eligibility_reason
            END,
            loaded_at = NOW()
    """)

    records = []

    for row in metadata.itertuples(index=False):
        security_type, reason = classify_security(
            row.company_name,
            row.sector_name,
            optional_string(row.industry_name),
            optional_string(row.quote_type),
        )

        is_eligible = bool(row.is_eligible)

        if row.symbol in overrides:
            override = overrides[row.symbol]

            security_type = override["security_type"]
            reason = override["eligibility_reason"]

            override_eligible = str(override["is_eligible"]).strip().lower()

            if override_eligible not in {"true", "false"}:
                raise ValueError(
                    f"Invalid eligibility override for {row.symbol}"
                )

            is_eligible = (
                is_eligible and override_eligible == "true"
            )

        records.append({
            "symbol": row.symbol,
            "company_name": row.company_name,
            "sector_name": row.sector_name,
            "market_cap": int(row.market_cap),
            "is_eligible": is_eligible,
            "security_type": security_type,
            "eligibility_reason": reason,
            "quote_type": optional_string(row.quote_type),
            "industry_name": optional_string(row.industry_name),
        })

    with engine.begin() as connection:
        connection.execute(query, records)

    print(f"Metadata records loaded: {len(records)}")
    eligible_count = sum(record["is_eligible"] for record in records)
    print(f"Eligible: {eligible_count}")
    print(f"Excluded: {len(records) - eligible_count}")


if __name__ == "__main__":
    main()
