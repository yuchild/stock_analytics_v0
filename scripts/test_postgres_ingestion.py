from stock_analytics.ingestion.yfinance_client import (
    fetch_stock_prices,
    validate_stock_prices,
)
from stock_analytics.ingestion.postgres_loader import load_stock_prices


INTERVALS = ["1m", "5m", "15m", "1h", "1d", "1wk", "1mo"]


if __name__ == "__main__":
    symbol = "AAPL"

    for interval in INTERVALS:
        try:
            df = fetch_stock_prices(symbol, interval)
            df = validate_stock_prices(df)

            loaded = load_stock_prices(df)

            print(f"SUCCESS: {symbol} {interval}: {loaded} rows upserted")

        except Exception as exc:
            print(f"ERROR: {symbol} {interval}: {exc}")
            raise