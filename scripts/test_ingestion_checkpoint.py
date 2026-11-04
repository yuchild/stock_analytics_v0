from stock_analytics.db.connection import get_latest_timestamp


if __name__ == "__main__":
    for symbol, interval in [
        ("AAPL", "1m"),
        ("AAPL", "1d"),
        ("AAPL", "1mo"),
        ("MSFT", "1d"),
    ]:
        latest = get_latest_timestamp(symbol, interval)

        print(
            f"{symbol:5} | {interval:3} | "
            f"Latest: {latest}"
        )