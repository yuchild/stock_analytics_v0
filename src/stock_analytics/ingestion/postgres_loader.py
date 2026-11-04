
import pandas as pd
from sqlalchemy import text

from stock_analytics.db.connection import engine


UPSERT_SQL = text("""
    INSERT INTO raw.stock_prices (
        symbol, interval_code, bar_timestamp,
        open_price, high_price, low_price, close_price,
        adj_close_price, volume
    )
    VALUES (
        :symbol, :interval_code, :bar_timestamp,
        :open_price, :high_price, :low_price, :close_price,
        :adj_close_price, :volume
    )
    ON CONFLICT (symbol, interval_code, bar_timestamp)
    DO UPDATE SET
        open_price = EXCLUDED.open_price,
        high_price = EXCLUDED.high_price,
        low_price = EXCLUDED.low_price,
        close_price = EXCLUDED.close_price,
        adj_close_price = EXCLUDED.adj_close_price,
        volume = EXCLUDED.volume,
        ingested_at = NOW()
""")


def load_stock_prices(df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    symbol = str(df["symbol"].iloc[0]).upper()

    columns = [
        "symbol", "interval_code", "bar_timestamp",
        "open_price", "high_price", "low_price",
        "close_price", "adj_close_price", "volume",
    ]

    data = df.reindex(columns=columns).copy()
    data = data.astype(object).where(pd.notna(data), None)

    records = data.to_dict(orient="records")

    # Convert pandas timestamps and NumPy scalars.
    for record in records:
        for key, value in record.items():
            if isinstance(value, pd.Timestamp):
                record[key] = value.to_pydatetime()
            elif hasattr(value, "item"):
                record[key] = value.item()

    with engine.begin() as connection:
        # The stock must exist before inserting price records.
        connection.execute(
            text("""
                INSERT INTO mart.symbols (symbol)
                VALUES (:symbol)
                ON CONFLICT (symbol) DO NOTHING
            """),
            {"symbol": symbol},
        )

        connection.execute(UPSERT_SQL, records)

    return len(records)
