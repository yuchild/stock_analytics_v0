
from unittest.mock import patch

import pandas as pd

from stock_analytics.ingestion.yfinance_client import (
    fetch_stock_prices_with_retry,
)


def test_recovery():
    """Two failures followed by a successful download."""
    sample = pd.DataFrame({"close_price": [100.0]})

    with (
        patch(
            "stock_analytics.ingestion.yfinance_client.fetch_stock_prices",
            side_effect=[
                ConnectionError("Temporary network failure"),
                ConnectionError("Temporary network failure"),
                sample,
            ],
        ) as mock_fetch,
        patch(
            "stock_analytics.ingestion.yfinance_client.time.sleep"
        ) as mock_sleep,
    ):
        result = fetch_stock_prices_with_retry(
            "AAPL", "1d", max_attempts=3
        )

        assert mock_fetch.call_count == 3
        assert mock_sleep.call_count == 2
        assert result.equals(sample)

    print("PASS: Recovered after two failures")


def test_exhausted_retries():
    """Three consecutive failures must raise an exception."""
    with (
        patch(
            "stock_analytics.ingestion.yfinance_client.fetch_stock_prices",
            side_effect=ConnectionError("Network unavailable"),
        ) as mock_fetch,
        patch(
            "stock_analytics.ingestion.yfinance_client.time.sleep"
        ) as mock_sleep,
    ):
        try:
            fetch_stock_prices_with_retry(
                "AAPL", "1d", max_attempts=3
            )
        except ConnectionError:
            pass
        else:
            raise AssertionError(
                "Expected ConnectionError after three failures"
            )

        assert mock_fetch.call_count == 3
        assert mock_sleep.call_count == 2

    print("PASS: Stopped after maximum retries")


if __name__ == "__main__":
    test_recovery()
    test_exhausted_retries()
