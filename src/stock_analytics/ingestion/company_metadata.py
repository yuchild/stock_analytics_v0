
import yfinance as yf

from pathlib import Path
import pandas as pd

YAHOO_TO_GICS_SECTOR = {
    "Basic Materials": "Materials",
    "Communication Services": "Communication Services",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Energy": "Energy",
    "Financial Services": "Financials",
    "Healthcare": "Health Care",
    "Industrials": "Industrials",
    "Real Estate": "Real Estate",
    "Technology": "Information Technology",
    "Utilities": "Utilities",
}


def normalize_yahoo_symbol(symbol: str) -> str:
    """Convert exchange ticker notation to Yahoo Finance notation."""
    return symbol.strip().upper().replace(".", "-")

GICS_MAPPING_PATH = Path(
    "data/processed/sp500_gics_mapping.csv"
)


def lookup_gics_sector(symbol: str) -> str | None:
    """Look up a sector in the local S&P 500 GICS reference."""

    if not GICS_MAPPING_PATH.exists():
        return None

    df = pd.read_csv(
        GICS_MAPPING_PATH,
        dtype={"symbol": str},
    )

    matches = df.loc[
        df["symbol"].str.strip().str.upper() == symbol.strip().upper(),
        "gics_sector",
    ]

    if matches.empty:
        return None

    return matches.iloc[0]


def fetch_company_metadata(symbol: str) -> dict:
    """Fetch company metadata from Yahoo Finance."""

    yahoo_symbol = normalize_yahoo_symbol(symbol)

    ticker = yf.Ticker(yahoo_symbol)
    info = ticker.info

    if not info:
        raise ValueError(f"No metadata returned for {symbol}")

    company_name = info.get("longName") or info.get("shortName")
    yahoo_sector = info.get("sector")
    sector_name = (
        lookup_gics_sector(symbol)
        or YAHOO_TO_GICS_SECTOR.get(yahoo_sector)
    )
    market_cap = info.get("marketCap")

    quote_type = info.get("quoteType")
    industry_name = info.get("industry")

    if not company_name or not sector_name or market_cap is None:
        raise ValueError(
            f"Incomplete metadata for {symbol}: "
            f"name={company_name}, sector={sector_name}, "
            f"market_cap={market_cap}"
        )

    if int(market_cap) <= 0:
        raise ValueError(
            f"Invalid market capitalization for {symbol}"
        )

    return {
        "symbol": symbol.upper(),
        "company_name": company_name,
        "sector_name": sector_name,
        "market_cap": int(market_cap),
        "quote_type": quote_type,
        "industry_name": industry_name,
    }
