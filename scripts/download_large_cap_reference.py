import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_URL = (
    "https://companiesmarketcap.com/usa/"
    "largest-companies-in-the-usa-by-market-cap/"
)

OUTPUT = Path("data/external/us_large_cap_reference.csv")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--delay", type=float, default=3.0)
    args = parser.parse_args()

    if args.pages < 1 or args.delay < 1:
        parser.error("--pages must be >= 1 and --delay >= 1")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "stock-analytics-research/0.1"
    })

    robots_response = session.get(
        "https://companiesmarketcap.com/robots.txt",
        timeout=30,
    )
    robots_response.raise_for_status()

    robots = RobotFileParser()
    robots.parse(robots_response.text.splitlines())

    records = []
    fetched_at = datetime.now(timezone.utc).isoformat()

    for page in range(1, args.pages + 1):
        url = BASE_URL if page == 1 else f"{BASE_URL}?page={page}"

        if not robots.can_fetch("*", url):
            raise RuntimeError(f"Disallowed by robots.txt: {url}")

        response = session.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")

        if table is None:
            raise RuntimeError(f"No ranking table found: {url}")

        page_records = []

        for row in table.select("tbody tr"):
            name_cell = row.select_one("td.name-td")
            rank_cell = row.select_one("td.rank-td")

            if name_cell is None or rank_cell is None:
                continue

            name = name_cell.select_one(".company-name")
            ticker = name_cell.select_one(".company-code")

            if name is None or ticker is None:
                continue

            market_cap = None

            for cell in row.find_all("td"):
                value = cell.get("data-sort")

                if value and value.isdigit() and int(value) >= 1_000_000:
                    market_cap = int(value)
                    break

            if market_cap is None:
                continue

            page_records.append({
                "symbol": ticker.get_text(strip=True),
                "company_name": name.get_text(strip=True),
                "market_cap": market_cap,
                "source": "CompaniesMarketCap",
                "source_url": url,
                "fetched_at": fetched_at,
            })

        if not page_records:
            raise RuntimeError(f"No companies parsed: {url}")

        records.extend(page_records)
        print(f"Page {page}: {len(page_records)} companies")

        if page < args.pages:
            time.sleep(args.delay)

    df = pd.DataFrame(records)

    df = (
        df.sort_values("market_cap", ascending=False)
        .drop_duplicates("symbol")
        .reset_index(drop=True)
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)

    print(f"\nUnique companies: {len(df):,}")
    print(f"Saved: {OUTPUT}")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
