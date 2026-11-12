#!/usr/bin/env python3
"""Read-only stock-price quality report for stock_analytics_v0.

Run from the repository root:
    PYTHONPATH=src .venv/bin/python scripts/check_price_data_quality.py --date 2026-11-09

Exit codes: 0 = no detected issues, 1 = quality warnings, 2 = configuration/error.
A missing minute candle is not automatically an error: no-trade minutes can be absent.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd
from sqlalchemy import text

from stock_analytics.db.connection import engine

INTERVALS = ("1m", "5m", "15m", "1h", "1d", "1wk", "1mo")
INTRADAY = ("1m", "5m", "15m", "1h")
UTC = ZoneInfo("UTC")
NY = ZoneInfo("America/New_York")


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as connection:
        return pd.read_sql_query(text(sql), connection, params=params or {})


def print_section(title: str, frame: pd.DataFrame, limit: int = 30) -> None:
    print(f"\n--- {title} ---")
    if frame.empty:
        print("None")
    else:
        print(frame.head(limit).to_string(index=False))
        if len(frame) > limit:
            print(f"... {len(frame) - limit} additional rows")


def session_bounds(session_date: date, calendar):
    session = pd.Timestamp(session_date)
    if not calendar.is_session(session):
        raise ValueError(f"{session_date} is not an XNYS trading session")
    opening = pd.Timestamp(calendar.session_open(session)).to_pydatetime()
    closing = pd.Timestamp(calendar.session_close(session)).to_pydatetime()
    return opening, closing


def run(session_date: date, max_rows: int, min_intraday_pct: float) -> int:
    calendar = xcals.get_calendar("XNYS")
    opening, closing = session_bounds(session_date, calendar)
    # Daily bars in this warehouse use UTC-midnight session dates.
    day_start = pd.Timestamp(session_date, tz="UTC").to_pydatetime()
    day_end = (pd.Timestamp(session_date, tz="UTC") + pd.Timedelta(days=1)).to_pydatetime()

    print(f"Stock price quality report | NYSE session {session_date}")
    print(f"Regular session: {opening.astimezone(NY)} to {closing.astimezone(NY)}")
    print("Daily-bar convention: UTC calendar date = exchange trading date")

    universe = query_df("""
        SELECT DISTINCT symbol
        FROM mart.v_sector_top20_candidates_v2
        ORDER BY symbol
    """)
    expected = set(universe["symbol"].astype(str))
    print(f"Expected universe: {len(expected)} symbols")
    if not expected:
        raise ValueError("Top-20 candidate view returned no symbols")

    daily = query_df("""
        SELECT p.symbol, p.bar_timestamp, p.open_price, p.high_price,
               p.low_price, p.close_price, p.volume
        FROM raw.stock_prices p
        JOIN mart.v_sector_top20_candidates_v2 u ON u.symbol = p.symbol
        WHERE p.interval_code = '1d'
          AND p.bar_timestamp >= :day_start
          AND p.bar_timestamp < :day_end
    """, {"day_start": day_start, "day_end": day_end})
    present = set(daily["symbol"].astype(str)) if not daily.empty else set()
    missing = sorted(expected - present)
    print(f"\nDAILY COVERAGE: {len(present)}/{len(expected)} symbols")
    if missing:
        print("Missing daily symbols:", ", ".join(missing))
    else:
        print("Missing daily symbols: none")

    zero_volume = daily.loc[daily["volume"].notna() & (daily["volume"] == 0)].copy()
    print_section("Zero-volume daily bars (review; not automatically invalid)",
                  zero_volume[["symbol", "bar_timestamp", "close_price", "volume"]]
                  if not zero_volume.empty else zero_volume, max_rows)

    # Compare actual regular-session bar counts to the expected number of time slots.
    # 1h uses 7 slots on a normal 390-minute session; partial closing slots are valid.
    duration_minutes = int((closing - opening).total_seconds() // 60)
    expected_slots = {
        "1m": duration_minutes,
        "5m": (duration_minutes + 4) // 5,
        "15m": (duration_minutes + 14) // 15,
        "1h": (duration_minutes + 59) // 60,
    }
    intraday = query_df("""
        SELECT p.symbol, p.interval_code, COUNT(*)::integer AS bars,
               MIN(p.bar_timestamp) AS first_bar,
               MAX(p.bar_timestamp) AS last_bar
        FROM raw.stock_prices p
        JOIN mart.v_sector_top20_candidates_v2 u ON u.symbol = p.symbol
        WHERE p.interval_code IN ('1m', '5m', '15m', '1h')
          AND p.bar_timestamp >= :session_open
          AND p.bar_timestamp < :session_close
        GROUP BY p.symbol, p.interval_code
    """, {"session_open": opening, "session_close": closing})
    index = {(str(r.symbol), str(r.interval_code)): int(r.bars)
             for r in intraday.itertuples(index=False)}
    coverage_rows = []
    absent_rows = []
    sparse_rows = []
    for interval in INTRADAY:
        counts = [index.get((symbol, interval), 0) for symbol in expected]
        covered = sum(count > 0 for count in counts)
        coverage_rows.append({"interval": interval, "symbols_with_bars": covered,
                              "expected_symbols": len(expected), "total_bars": sum(counts),
                              "expected_slots_per_symbol": expected_slots[interval]})
        for symbol in sorted(expected):
            count = index.get((symbol, interval), 0)
            if count == 0:
                absent_rows.append({"symbol": symbol, "interval": interval})
            elif count / expected_slots[interval] * 100 < min_intraday_pct:
                sparse_rows.append({"symbol": symbol, "interval": interval,
                                    "bars": count, "slots": expected_slots[interval],
                                    "pct": round(100 * count / expected_slots[interval], 1)})
    print_section("Intraday session coverage", pd.DataFrame(coverage_rows), max_rows)
    print_section("Missing entire intraday session", pd.DataFrame(absent_rows), max_rows)
    print_section(f"Sparse intraday sessions (<{min_intraday_pct:g}% of slots; advisory)",
                  pd.DataFrame(sparse_rows).sort_values("pct") if sparse_rows else pd.DataFrame(),
                  max_rows)

    # Freshness is measured as of the requested session, not today's live market.
    freshness = query_df("""
        SELECT u.symbol, i.interval_code, MAX(p.bar_timestamp) AS latest_bar
        FROM (SELECT DISTINCT symbol FROM mart.v_sector_top20_candidates_v2) u
        CROSS JOIN (VALUES ('1m'), ('5m'), ('15m'), ('1h'), ('1d')) AS i(interval_code)
        LEFT JOIN raw.stock_prices p
          ON p.symbol = u.symbol AND p.interval_code = i.interval_code
         AND p.bar_timestamp < :cutoff
        GROUP BY u.symbol, i.interval_code
    """, {"cutoff": max(closing, day_end)})
    # A bar from the requested session is the basic freshness requirement.
    stale = []
    for row in freshness.itertuples(index=False):
        key = (str(row.symbol), str(row.interval_code))
        if row.interval_code == "1d":
            current = str(row.symbol) in present
        else:
            current = index.get(key, 0) > 0
        if not current:
            stale.append({"symbol": row.symbol, "interval": row.interval_code,
                          "latest_stored_bar": row.latest_bar})
    print_section("Stale / missing session data", pd.DataFrame(stale), max_rows)

    # OHLCV integrity on all seven intervals in a bounded window; includes the session.
    integrity = query_df("""
        SELECT p.symbol, p.interval_code, p.bar_timestamp,
               p.open_price, p.high_price, p.low_price, p.close_price, p.volume
        FROM raw.stock_prices p
        JOIN mart.v_sector_top20_candidates_v2 u ON u.symbol = p.symbol
        WHERE p.bar_timestamp >= :window_start AND p.bar_timestamp < :window_end
          AND (
            p.open_price IS NULL OR p.high_price IS NULL OR
            p.low_price IS NULL OR p.close_price IS NULL OR
            p.open_price <= 0 OR p.high_price <= 0 OR
            p.low_price <= 0 OR p.close_price <= 0 OR
            p.high_price < GREATEST(p.open_price, p.close_price, p.low_price) OR
            p.low_price > LEAST(p.open_price, p.close_price, p.high_price) OR
            p.volume < 0
          )
        ORDER BY p.symbol, p.interval_code, p.bar_timestamp
    """, {"window_start": day_start - pd.Timedelta(days=35),
          "window_end": max(day_end, closing)})
    print_section("Invalid OHLCV bars (last 35 days)", integrity, max_rows)

    issues = len(missing) + len(zero_volume) + len(absent_rows) + len(sparse_rows) + len(integrity)
    print(f"\nQUALITY SUMMARY: {issues} flagged findings ")
    print("Warnings are not automatically ingestion failures; investigate before altering bars.")
    return 1 if issues else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=date.fromisoformat,
                        help="Completed NYSE session YYYY-MM-DD")
    parser.add_argument("--max-rows", type=int, default=30)
    parser.add_argument("--min-intraday-pct", type=float, default=80.0,
                        help="Advisory sparse-bar threshold (default 80)")
    args = parser.parse_args()
    if args.max_rows < 1 or not 0 <= args.min_intraday_pct <= 100:
        parser.error("--max-rows must be >=1 and --min-intraday-pct must be 0..100")
    try:
        return run(args.date, args.max_rows, args.min_intraday_pct)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
