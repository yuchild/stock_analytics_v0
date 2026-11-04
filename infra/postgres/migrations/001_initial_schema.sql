BEGIN;

-- Logical data layers
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS ml;

-- Business sectors
CREATE TABLE IF NOT EXISTS mart.sectors (
    sector_id SMALLSERIAL PRIMARY KEY,
    sector_name VARCHAR(100) NOT NULL UNIQUE
);

-- Stock universe
CREATE TABLE IF NOT EXISTS mart.symbols (
    symbol VARCHAR(20) PRIMARY KEY,
    company_name TEXT,
    sector_id SMALLINT REFERENCES mart.sectors(sector_id),
    market_cap BIGINT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_symbols_sector
    ON mart.symbols (sector_id, market_cap DESC);

-- Supported intervals
CREATE TABLE IF NOT EXISTS mart.intervals (
    interval_code VARCHAR(5) PRIMARY KEY,
    description TEXT NOT NULL
);

INSERT INTO mart.intervals (interval_code, description)
VALUES
    ('1m', 'One minute'),
    ('5m', 'Five minutes'),
    ('15m', 'Fifteen minutes'),
    ('1h', 'One hour'),
    ('1d', 'One day'),
    ('1wk', 'One week'),
    ('1mo', 'One month')
ON CONFLICT (interval_code) DO NOTHING;

-- Raw OHLCV price history
CREATE TABLE IF NOT EXISTS raw.stock_prices (
    symbol VARCHAR(20) NOT NULL
        REFERENCES mart.symbols(symbol),

    interval_code VARCHAR(5) NOT NULL
        REFERENCES mart.intervals(interval_code),

    bar_timestamp TIMESTAMPTZ NOT NULL,

    open_price NUMERIC(18,6),
    high_price NUMERIC(18,6),
    low_price NUMERIC(18,6),
    close_price NUMERIC(18,6),
    adj_close_price NUMERIC(18,6),
    volume BIGINT,

    data_source VARCHAR(50) NOT NULL DEFAULT 'yfinance',
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (symbol, interval_code, bar_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_stock_prices_interval_time
    ON raw.stock_prices (interval_code, bar_timestamp DESC);

-- Ingestion audit log
CREATE TABLE IF NOT EXISTS analytics.ingestion_log (
    ingestion_id BIGSERIAL PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20),
    interval_code VARCHAR(5),
    rows_fetched INTEGER NOT NULL DEFAULT 0,
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ingestion_log_started
    ON analytics.ingestion_log (started_at DESC);

COMMIT;
