
import argparse
from stock_analytics.db.connection import get_latest_timestamp

from stock_analytics.ingestion.yfinance_client import (
    INTERVAL_PERIODS,
    fetch_stock_prices,
    validate_stock_prices,
    fetch_stock_prices_with_retry,
)
from stock_analytics.ingestion.postgres_loader import load_stock_prices
from stock_analytics.ingestion.ingestion_logger import log_ingestion


def run_ingestion(
        symbol: str,
        interval: str,
        backfill: bool = False,
    ):
    rows_fetched = 0
    rows_loaded = 0
    status = "success"
    error_message = None

    try:
        latest_timestamp = (
            None if backfill
            else get_latest_timestamp(symbol, interval)
        )

        df = fetch_stock_prices_with_retry(
            symbol,
            interval,
            latest_timestamp=latest_timestamp,
            max_attempts=3,
        )
        rows_fetched = len(df)

        df = validate_stock_prices(df)

        if df.empty:
            raise ValueError("No valid price records returned")

        rows_loaded = load_stock_prices(df)

        print(
            f"SUCCESS: {symbol} {interval} "
            f"fetched={rows_fetched} loaded={rows_loaded}"
        )

    except Exception as exc:
        status = "failed"
        error_message = str(exc)
        print(f"FAILED: {symbol} {interval}: {exc}")

    finally:
        log_ingestion(
            pipeline_name="yfinance_ingestion",
            symbol=symbol,
            interval=interval,
            rows_fetched=rows_fetched,
            rows_loaded=rows_loaded,
            status=status,
            error_message=error_message,
            ingestion_mode="backfill" if backfill else "incremental",
            requested_period=(
                INTERVAL_PERIODS[interval] if backfill else None
            ),
        )

    if status == "failed":
        raise RuntimeError(error_message)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--interval", default="1d")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Download historical data instead of using the latest checkpoint",
    )

    args = parser.parse_args()

    run_ingestion(
        args.symbol.upper(),
        args.interval,
        backfill=args.backfill,
    )
