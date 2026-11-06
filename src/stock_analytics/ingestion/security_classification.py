
import re
import pandas as pd

def classify_security(
    company_name: str,
    sector_name: str,
    industry_name: str | None,
    quote_type: str | None,
) -> tuple[str, str]:
    """Return normalized security type and classification reason."""

    name = str(company_name).lower() if pd.notna(company_name) else ""
    sector = str(sector_name) if pd.notna(sector_name) else ""
    industry = str(industry_name).lower() if pd.notna(industry_name) else ""
    quote = str(quote_type).upper() if pd.notna(quote_type) else ""

    if quote in {"ETF", "MUTUALFUND"}:
        return "fund", f"Yahoo quote type: {quote}"

    if industry.startswith("reit -"):
        return "reit", f"Yahoo industry: {industry_name}"

    if re.search(
        r"\b(closed[- ]end fund|investment fund|income fund)\b",
        name,
    ):
        return "fund", "Company name indicates investment fund"

    if quote == "EQUITY" and sector:
        return "operating_company", "Yahoo equity classification"

    return "review", "Insufficient classification information"