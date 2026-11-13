\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '120s';
DO $$
DECLARE
  old_count integer;
  nws_intervals integer;
  roku_metadata integer;
  nws_metadata integer;
BEGIN
  SELECT count(*) INTO old_count FROM mart.v_sector_top20_candidates_v2;
  IF old_count <> 220 THEN
    RAISE EXCEPTION 'Expected 220 current universe rows, got %', old_count;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM mart.v_sector_top20_candidates_v2 WHERE symbol='ROKU') THEN
    RAISE EXCEPTION 'ROKU is not currently in top 20 universe';
  END IF;
  IF EXISTS (SELECT 1 FROM mart.v_sector_top20_candidates_v2 WHERE symbol='NWS') THEN
    RAISE EXCEPTION 'NWS already in top 20 universe';
  END IF;
  SELECT count(DISTINCT interval_code) INTO nws_intervals FROM raw.stock_prices WHERE symbol='NWS';
  IF nws_intervals <> 7 THEN
    RAISE EXCEPTION 'NWS backfill has % intervals, expected 7', nws_intervals;
  END IF;
  SELECT count(*) INTO roku_metadata FROM staging.company_metadata WHERE symbol='ROKU';
  SELECT count(*) INTO nws_metadata FROM staging.company_metadata WHERE symbol='NWS' AND is_eligible=true;
  IF roku_metadata <> 1 OR nws_metadata <> 1 THEN
    RAISE EXCEPTION 'Unexpected metadata rows: ROKU %, eligible NWS %', roku_metadata, nws_metadata;
  END IF;
END $$;
-- Exclude ROKU from ranking; preserves a metadata tombstone for audit purposes.
UPDATE staging.company_metadata SET is_eligible=false WHERE symbol='ROKU';
-- Delete ROKU price history as requested.
DELETE FROM raw.stock_prices WHERE symbol='ROKU';
-- Deactivate ROKU in symbol registry if present. No assumption about foreign keys.
UPDATE mart.symbols SET is_active=false, updated_at=now() WHERE symbol='ROKU';
-- If NWS exists in the registry, activate it. Ingestion may manage inserts separately.
UPDATE mart.symbols SET is_active=true, updated_at=now() WHERE symbol='NWS';
DO $$
DECLARE
  total integer;
  sectors integer;
  comm_count integer;
BEGIN
  SELECT count(*), count(DISTINCT symbol) INTO total, sectors FROM mart.v_sector_top20_candidates_v2;
  IF total <> 220 OR sectors <> 220 THEN
    RAISE EXCEPTION 'Post-change universe invalid: rows %, distinct symbols %', total, sectors;
  END IF;
  IF EXISTS (SELECT 1 FROM mart.v_sector_top20_candidates_v2 WHERE symbol='ROKU') OR
     NOT EXISTS (SELECT 1 FROM mart.v_sector_top20_candidates_v2 WHERE symbol='NWS') THEN
    RAISE EXCEPTION 'ROKU exclusion / NWS promotion failed';
  END IF;
  SELECT count(*) INTO comm_count FROM mart.v_sector_top20_candidates_v2 WHERE sector_name='Communication Services';
  IF comm_count <> 20 THEN
    RAISE EXCEPTION 'Communication Services has % companies, expected 20', comm_count;
  END IF;
  IF EXISTS (SELECT 1 FROM raw.stock_prices WHERE symbol='ROKU') THEN
    RAISE EXCEPTION 'ROKU prices remain';
  END IF;
END $$;
COMMIT;
SELECT sector_rank, symbol, company_name FROM mart.v_sector_top20_candidates_v2 WHERE sector_name='Communication Services' ORDER BY sector_rank;
SELECT symbol, is_eligible FROM staging.company_metadata WHERE symbol IN ('ROKU','NWS');
SELECT symbol, is_active FROM mart.symbols WHERE symbol IN ('ROKU','NWS');
