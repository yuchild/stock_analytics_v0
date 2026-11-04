import pandas as pd
import yfinance as yf

import time
import random


INTERVAL_PERIODS = {
    "1m": "5d",
    "5m": "1mo",
    "15m": "1mo",
    "1h": "3mo",
    "1d": "1y",
    "1wk": "5y",
    "1mo": "max",
}


INCREMENTAL_OVERLAP = {
    "1m": pd.Timedelta(days=2),
    "5m": pd.Timedelta(days=5),
    "15m": pd.Timedelta(days=5),
    "1h": pd.Timedelta(days=7),
    "1d": pd.Timedelta(days=7),
    "1wk": pd.Timedelta(weeks=4),
    "1mo": pd.Timedelta(days=90),
}



def get_incremental_start(latest_timestamp, interval: str):
    """Calculate a safe incremental start timestamp."""

    latest = pd.Timestamp(latest_timestamp)

    if latest.tzinfo is None:
        latest = latest.tz_localize("UTC")

    latest_utc = latest.tz_convert("UTC")

    if interval == "1d":
        start_date = latest_utc.date() - pd.Timedelta(days=7)

    elif interval == "1wk":
        start_date = latest_utc.date() - pd.Timedelta(weeks=5)

    elif interval == "1mo":
        month_start = latest_utc.date().replace(day=1)
        start_date = month_start - pd.DateOffset(months=3)

    else:
        return latest - INCREMENTAL_OVERLAP[interval]

    return pd.Timestamp(start_date).tz_localize("UTC")


def fetch_stock_prices(
    symbol: str,
    interval: str,
    latest_timestamp=None,
) -> pd.DataFrame:
    if interval not in INTERVAL_PERIODS:
        raise ValueError(f"Unsupported interval: {interval}")

    kwargs = {
        "tickers": symbol,
        "interval": interval,
        "auto_adjust": False,
        "progress": False,
        "threads": False,
    }

    if latest_timestamp is None:
        kwargs["period"] = INTERVAL_PERIODS[interval]
        print(f"Full download: {symbol} {interval}")
    else:
        start = get_incremental_start(latest_timestamp, interval)

        # Yahoo Finance requires timezone-aware intraday timestamps.
        if start.tzinfo is None:
            start = start.tz_localize("UTC")

        kwargs["start"] = start.to_pydatetime()
        print(f"Incremental download: {symbol} {interval}, start={start}")

    df = yf.download(**kwargs)

    if df.empty:
        print(f"No data returned for {symbol} ({interval})")
        return df

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()

    df.columns = [
        str(column).strip().lower().replace(" ", "_")
        for column in df.columns
    ]

    df = df.rename(
        columns={
            "date": "bar_timestamp",
            "datetime": "bar_timestamp",
            "open": "open_price",
            "high": "high_price",
            "low": "low_price",
            "close": "close_price",
            "adj_close": "adj_close_price",
        }
    )

    df["bar_timestamp"] = pd.to_datetime(
        df["bar_timestamp"],
        utc=True,
    )

    df["symbol"] = symbol.upper()
    df["interval_code"] = interval

    return df


def fetch_stock_prices_with_retry(
    symbol: str,
    interval: str,
    latest_timestamp=None,
    max_attempts: int = 3,
) -> pd.DataFrame:
    """Retry transient download failures with exponential backoff."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    for attempt in range(1, max_attempts + 1):
        try:
            df = fetch_stock_prices(
                symbol,
                interval,
                latest_timestamp=latest_timestamp,
            )

            if df.empty:
                raise ValueError(
                    f"Empty response for {symbol} ({interval})"
                )

            return df

        except Exception as exc:
            print(
                f"Attempt {attempt}/{max_attempts} failed "
                f"for {symbol} {interval}: {exc}"
            )

            if attempt == max_attempts:
                raise

            delay = min(2 ** (attempt - 1), 30)
            delay += random.uniform(0, 0.5)

            print(f"Retrying in {delay:.1f} seconds...")
            time.sleep(delay)

    raise RuntimeError("Unexpected retry termination")


def validate_stock_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Remove invalid OHLCV records before database ingestion."""

    if df.empty:
        return df

    original_count = len(df)

    required_columns = [
        "bar_timestamp",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
    ]

    # Remove rows with missing essential values.
    df = df.dropna(subset=required_columns).copy()

    # Ensure OHLC values are positive.
    price_columns = [
        "open_price",
        "high_price",
        "low_price",
        "close_price",
    ]

    df = df[(df[price_columns] > 0).all(axis=1)].copy()

    # Ensure high/low values are internally consistent.
    df = df[
        (df["high_price"] >= df[["open_price", "close_price", "low_price"]].max(axis=1))
        & (df["low_price"] <= df[["open_price", "close_price", "high_price"]].min(axis=1))
    ].copy()

    # Remove negative volume.
    df = df[df["volume"].isna() | (df["volume"] >= 0)].copy()

    # Remove duplicate candles.
    df = df.drop_duplicates(
        subset=["symbol", "interval_code", "bar_timestamp"],
        keep="last",
    )

    removed = original_count - len(df)

    print(f"Validation: {len(df)} valid rows; {removed} removed")

    return df