
from sqlalchemy import text

from stock_analytics.db.connection import engine


UPSERT_METADATA_SQL = text("""
    INSERT INTO mart.symbols (
        symbol,
        company_name,
        sector_id,
        market_cap,
        updated_at
    )
    SELECT
        :symbol,
        :company_name,
        s.sector_id,
        :market_cap,
        NOW()
    FROM mart.sectors s
    WHERE s.sector_name = :sector_name

    ON CONFLICT (symbol)
    DO UPDATE SET
        company_name = EXCLUDED.company_name,
        sector_id = EXCLUDED.sector_id,
        market_cap = EXCLUDED.market_cap,
        updated_at = NOW()
""")


def load_company_metadata(metadata: dict) -> None:
    """Insert or update company metadata in PostgreSQL."""

    with engine.begin() as connection:
        result = connection.execute(
            UPSERT_METADATA_SQL,
            metadata,
        )

        if result.rowcount != 1:
            raise ValueError(
                "Metadata was not saved. "
                f"Check sector: {metadata['sector_name']}"
            )
