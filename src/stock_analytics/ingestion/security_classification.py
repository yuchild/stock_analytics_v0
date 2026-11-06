
import re


def classify_security(
    company_name: str,
    sector_name: str,
    industry_name: str | None,
    quote_type: str | None,
) -> tuple[str, str]:
    """Return normalized security type and classification reason."""

    name = (company_name or "").lower()
    sector = sector_name or ""
    industry = (industry_name or "").lower()
    quote = (quote_type or "").upper()

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
        if industry in {"asset management", "capital markets"}:
            return (
                "review",
                "Financial industry requires additional verification",
            )

        return "operating_company", "Yahoo equity classification"

    return "review", "Insufficient classification information"
