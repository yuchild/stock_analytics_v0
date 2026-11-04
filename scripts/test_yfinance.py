from stock_analytics.ingestion.yfinance_client import (
    fetch_stock_prices,
    validate_stock_prices,
)


INTERVALS = ["1m", "5m", "15m", "1h", "1d", "1wk", "1mo"]


if __name__ == "__main__":
    for interval in INTERVALS:
        try:
            df = fetch_stock_prices("AAPL", interval)
            df = validate_stock_prices(df)

            print(f"\n{interval}: {len(df)} rows")

            if not df.empty:
                print(df[["bar_timestamp", "close_price", "volume"]].tail(3))

        except Exception as exc:
            print(f"ERROR [{interval}]: {exc}")

        print("-" * 60)