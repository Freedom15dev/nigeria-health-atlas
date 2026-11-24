"""Load hand-entered tables from data/manual/ and check every row is traceable.

Each manual file must have source_id, table and printed_page on every row.
nha.csv (National Health Accounts) is optional until the NHA PDF is in data/raw/.
"""
import sys

import pandas as pd

from common import MANUAL, load_sources

REQUIRED = ["source_id", "table", "printed_page"]


def check_manual(df: pd.DataFrame, name: str, sources: dict) -> list[str]:
    errors = []
    for c in REQUIRED:
        if c not in df.columns:
            errors.append(f"{name}: missing column {c}")
        elif df[c].isna().any() or (df[c].astype(str).str.strip() == "").any():
            errors.append(f"{name}: {int(df[c].isna().sum())} rows with no {c}")
    if "source_id" in df.columns:
        unknown = set(df["source_id"].dropna()) - set(sources)
        if unknown:
            errors.append(f"{name}: source_id not in sources.yaml: {sorted(unknown)}")
    return errors


def load_ndhs_manual() -> pd.DataFrame:
    return pd.read_csv(MANUAL / "ndhs2024_state.csv")


OWN_LAYOUT = {"headline_figures.csv", "income_benchmarks.csv"}


def main() -> None:
    sources = load_sources()
    errors = []
    # these files have their own layout (one row per quoted figure) and their own check in validate.py
    files = [f for f in sorted(MANUAL.glob("*.csv")) if f.name not in OWN_LAYOUT]
    if not (MANUAL / "ndhs2024_state.csv").exists():
        sys.exit("data/manual/ndhs2024_state.csv missing: run pipeline/transcribe_ndhs_pdf.py")
    for f in files:
        df = pd.read_csv(f)
        errors += check_manual(df, f.name, sources)
        print(f"  {f.name}: {len(df)} rows")
    if errors:
        sys.exit("Manual data problems:\n  " + "\n  ".join(errors))


if __name__ == "__main__":
    main()
