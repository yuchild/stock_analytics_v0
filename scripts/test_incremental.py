
from stock_analytics.db.connection import get_latest_timestamp
from stock_analytics.ingestion.yfinance_client import (
    fetch_stock_prices,
    validate_stock_prices,
)


for symbol, interval in [
    ("AAPL", "1m"),
    ("AAPL", "1d"),
    ("AAPL", "1mo"),
    ("MSFT", "1d"),
]:
    latest = get_latest_timestamp(symbol, interval)

    df = fetch_stock_prices(
        symbol,
        interval,
        latest_timestamp=latest,
    )

    df = validate_stock_prices(df)

    print(
        f"{symbol} {interval}: "
        f"checkpoint={latest}, "
        f"downloaded={len(df)} rows"
    )
    print("-" * 60)
