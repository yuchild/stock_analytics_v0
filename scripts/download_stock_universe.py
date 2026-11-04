
from pathlib import Path
from io import StringIO

import pandas as pd
import requests


BASE_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/"
OUTPUT_PATH = Path("data/external/us_stock_candidates.csv")


def download_directory(filename: str) -> pd.DataFrame:
    response = requests.get(
        BASE_URL + filename,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    df = pd.read_csv(StringIO(response.text), sep="|")
    df = df.loc[
        ~df.iloc[:, 0].astype(str).str.startswith("File Creation Time")
    ].copy()

    return df


def main():
    nasdaq = download_directory("nasdaqlisted.txt")
    other = download_directory("otherlisted.txt")

    nasdaq = nasdaq[
        (nasdaq["Test Issue"] == "N")
        & (nasdaq["ETF"] == "N")
    ].copy()

    other = other[
        (other["Test Issue"] == "N")
        & (other["ETF"] == "N")
    ].copy()

    nasdaq = nasdaq.rename(
        columns={
            "Symbol": "symbol",
            "Security Name": "security_name",
        }
    )

    other = other.rename(
        columns={
            "ACT Symbol": "symbol",
            "Security Name": "security_name",
        }
    )

    candidates = pd.concat(
        [
            nasdaq[["symbol", "security_name"]],
            other[["symbol", "security_name"]],
        ],
        ignore_index=True,
    )

    candidates = candidates.dropna(subset=["symbol"])
    candidates["symbol"] = candidates["symbol"].str.strip()

    candidates = candidates.drop_duplicates(subset=["symbol"])
    candidates = candidates.sort_values("symbol")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(OUTPUT_PATH, index=False)

    print(f"Nasdaq-listed securities: {len(nasdaq):,}")
    print(f"Other exchange securities: {len(other):,}")
    print(f"Unique candidates: {len(candidates):,}")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
