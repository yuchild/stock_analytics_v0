
import pandas as pd

INPUT = "data/processed/us_equity_candidates.csv"

df = pd.read_csv(INPUT, dtype=str).fillna("")

patterns = {
    "Preferred ticker ($)": r"\$",
    "Preferred shares": r"\bpreferred\b|\bpreference\b",
    "Depositary preferred": r"\bdepositary shares?\b",
    "Closed-end funds": r"\bclosed.end\b|\bclosed end\b",
    "Investment funds": r"\b(?:investment|income|opportunities) fund\b",
    "Trust funds": r"\b(?:income|investment) trust\b",
    "Units": r"\bunits?\b",
    "Warrants": r"\bwarrants?\b",
    "Rights": r"\brights?\b",
}

print(f"Total candidates: {len(df):,}\n")

for label, pattern in patterns.items():
    mask = (
        df["symbol"].str.contains(
            pattern, case=False, regex=True
        )
        if label == "Preferred ticker ($)"
        else df["security_name"].str.contains(
            pattern, case=False, regex=True
        )
    )

    print(f"{label:24} {mask.sum():5}")

    if mask.any():
        print(
            df.loc[mask, ["symbol", "security_name"]]
            .head(3)
            .to_string(index=False)
        )
        print()
