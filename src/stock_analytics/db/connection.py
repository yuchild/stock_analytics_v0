from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql+psycopg2:///stock_analytics_v0"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


def test_connection():
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT current_database(), current_user")
        )

        return result.fetchone()


def get_latest_timestamp(symbol: str, interval: str):
    """Return the most recent stored candle timestamp."""

    query = text("""
        SELECT MAX(bar_timestamp)
        FROM raw.stock_prices
        WHERE symbol = :symbol
          AND interval_code = :interval
    """)

    with engine.connect() as connection:
        return connection.execute(
            query,
            {
                "symbol": symbol.upper(),
                "interval": interval,
            },
        ).scalar_one()