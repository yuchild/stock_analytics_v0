
import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf
from sqlalchemy import bindparam, text

from stock_analytics.db.connection import engine
from stock_analytics.ingestion.company_metadata import (
    normalize_yahoo_symbol,
)
from stock_analytics.ingestion.security_classification import (
    classify_security,
)



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    overrides_path = Path(
        "data/reference/security_classification_overrides.csv"
    )

    overrides = pd.read_csv(
        overrides_path,
        dtype=str,
        keep_default_na=False,
    )

    if overrides["symbol"].duplicated().any():
        raise ValueError("Duplicate classification overrides")
    override_map = overrides.set_index("symbol").to_dict("index")

    if args.limit < 1:
        parser.error("--limit must be positive")

    if args.delay < 0:
        parser.error("--delay cannot be negative")

    failure_path = Path("data/processed/security_metadata_failures.csv")
    failure_path.parent.mkdir(parents=True, exist_ok=True)

    failed_symbols = set()

    if failure_path.exists():
        with failure_path.open(newline="") as file:
            reader = csv.DictReader(file)
            failed_symbols = {
                row["symbol"] for row in reader
            }

    # Avoid expanding an empty list into an integer-typed empty-set SQL expression.
    exclusion_clause = "AND symbol NOT IN :failed_symbols" if failed_symbols else ""
    statement = text(f"""
        SELECT symbol, company_name, sector_name,
               security_type, is_eligible
        FROM staging.company_metadata
        WHERE (quote_type IS NULL OR industry_name IS NULL)
        {exclusion_clause}
        ORDER BY market_cap DESC
        LIMIT :limit
    """)
    params = {"limit": args.limit}
    if failed_symbols:
        statement = statement.bindparams(bindparam("failed_symbols", expanding=True))
        params["failed_symbols"] = sorted(failed_symbols)

    with engine.connect() as connection:
        rows = connection.execute(statement, params).mappings().all()

    for row in rows:
        symbol = row["symbol"]

        try:
            info = yf.Ticker(
                normalize_yahoo_symbol(symbol)
            ).info

            quote_type = info.get("quoteType")
            industry_name = info.get("industry")

            if not quote_type or not industry_name:
                raise ValueError("Missing classification fields")

            security_type, reason = classify_security(
                row["company_name"],
                row["sector_name"],
                industry_name,
                quote_type,
            )

            # Preserve explicit classifications and exclusions.
            if symbol in override_map:
                security_type = override_map[symbol]["security_type"]
                reason = override_map[symbol]["eligibility_reason"]

            with engine.begin() as connection:
                connection.execute(text("""
                    UPDATE staging.company_metadata
                    SET quote_type = :quote_type,
                        industry_name = :industry_name,
                        security_type = :security_type,
                        eligibility_reason = :reason,
                        fetched_at = NOW(),
                        loaded_at = NOW()
                    WHERE symbol = :symbol
                """), {
                    "symbol": symbol,
                    "quote_type": quote_type,
                    "industry_name": industry_name,
                    "security_type": security_type,
                    "reason": reason,
                })

            print(
                f"{symbol}: {security_type} "
                f"({industry_name})"
            )

        except Exception as exc:
            error_message = str(exc).lower()

            if any(term in error_message for term in [
                "rate limit",
                "too many requests",
                "429",
            ]):
                print(
                    f"{symbol}: Yahoo rate limit detected. "
                    "Stopping batch to avoid further requests."
                )
                break
            
            with failure_path.open("a", newline="") as file:
                writer = csv.writer(file)

                if file.tell() == 0:
                    writer.writerow(["symbol", "error", "failed_at"])

                writer.writerow([
                    symbol,
                    str(exc),
                    datetime.now(timezone.utc).isoformat(),
                ])
            print(f"{symbol}: FAILED - {exc}")

        time.sleep(args.delay)


if __name__ == "__main__":
    main()
