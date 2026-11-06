CREATE OR REPLACE VIEW mart.v_sector_top20_candidates AS

WITH deduplicated AS (
    SELECT DISTINCT ON (sector_name, company_name)
        sector_name,
        company_name,
        symbol,
        market_cap,
        security_type,
        fetched_at
    FROM staging.company_metadata
    WHERE is_eligible = TRUE
      AND market_cap IS NOT NULL
      AND sector_name IS NOT NULL
    ORDER BY
        sector_name,
        company_name,
        market_cap DESC,
        symbol
),

ranked AS (
    SELECT
        sector_name,
        company_name,
        symbol,
        market_cap,
        security_type,
        fetched_at,
        ROW_NUMBER() OVER (
            PARTITION BY sector_name
            ORDER BY market_cap DESC, symbol
        ) AS sector_rank
    FROM deduplicated
)

SELECT
    sector_name,
    sector_rank,
    symbol,
    company_name,
    market_cap,
    security_type,
    fetched_at
FROM ranked
WHERE sector_rank <= 20;
