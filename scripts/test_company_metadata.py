
from stock_analytics.ingestion.company_metadata import (
    fetch_company_metadata,
)


if __name__ == "__main__":
    for symbol in ["AAPL", "MSFT", "NVDA"]:
        metadata = fetch_company_metadata(symbol)

        print(f"\nSymbol: {metadata['symbol']}")
        print(f"Company: {metadata['company_name']}")
        print(f"Sector: {metadata['sector_name']}")
        print(f"Market cap: ${metadata['market_cap']:,}")
