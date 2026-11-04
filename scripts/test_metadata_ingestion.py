
from stock_analytics.ingestion.company_metadata import (
    fetch_company_metadata,
)
from stock_analytics.ingestion.metadata_loader import (
    load_company_metadata,
)


if __name__ == "__main__":
    for symbol in ["AAPL", "MSFT", "NVDA"]:
        metadata = fetch_company_metadata(symbol)
        load_company_metadata(metadata)

        print(
            f"SUCCESS: {symbol} | "
            f"{metadata['company_name']} | "
            f"{metadata['sector_name']} | "
            f"${metadata['market_cap']:,}"
        )
