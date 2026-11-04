
import yfinance as yf


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


def fetch_company_metadata(symbol: str) -> dict:
    """Fetch company metadata from Yahoo Finance."""

    yahoo_symbol = normalize_yahoo_symbol(symbol)

    ticker = yf.Ticker(yahoo_symbol)
    info = ticker.info

    if not info:
        raise ValueError(f"No metadata returned for {symbol}")

    company_name = info.get("longName") or info.get("shortName")
    yahoo_sector = info.get("sector")
    sector_name = YAHOO_TO_GICS_SECTOR.get(yahoo_sector)
    market_cap = info.get("marketCap")

    if not company_name or not sector_name or market_cap is None:
        raise ValueError(
            f"Incomplete metadata for {symbol}: "
            f"name={company_name}, sector={sector_name}, "
            f"market_cap={market_cap}"
        )

    return {
        "symbol": symbol.upper(),
        "company_name": company_name,
        "sector_name": sector_name,
        "market_cap": int(market_cap),
    }
