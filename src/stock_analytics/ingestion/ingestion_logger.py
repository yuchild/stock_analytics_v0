
from sqlalchemy import text

from stock_analytics.db.connection import engine


def log_ingestion(
    pipeline_name: str,
    symbol: str,
    interval: str,
    rows_fetched: int,
    rows_loaded: int,
    status: str,
    error_message: str | None = None,
):
    query = text("""
        INSERT INTO analytics.ingestion_log (
            pipeline_name,
            symbol,
            interval_code,
            rows_fetched,
            rows_loaded,
            status,
            error_message,
            started_at,
            finished_at
        )
        VALUES (
            :pipeline_name,
            :symbol,
            :interval,
            :rows_fetched,
            :rows_loaded,
            :status,
            :error_message,
            NOW(),
            NOW()
        )
    """)

    with engine.begin() as connection:
        connection.execute(
            query,
            {
                "pipeline_name": pipeline_name,
                "symbol": symbol,
                "interval": interval,
                "rows_fetched": rows_fetched,
                "rows_loaded": rows_loaded,
                "status": status,
                "error_message": error_message,
            },
        )
