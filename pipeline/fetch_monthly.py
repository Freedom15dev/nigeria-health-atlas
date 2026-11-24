"""Monthly cost-pressure series (page 6), reused from the Money Matters project.

Money Matters (repo naija-money-dashboard) already pulls, cleans and documents the CBN
inflation feed and the CBN daily naira rate (monthly average). Rather than repeat that work,
this step copies its cleaned monthly panel, keeping the same cleaning and caveats.

- If the sibling repo is next to this one (../naija-money-dashboard) and its panel differs from
  the latest snapshot here, a new dated snapshot is saved in data/raw/.
- Otherwise (e.g. on GitHub Actions) the latest snapshot in data/raw/ is used as is.

Writes data/processed/monthly_prices.csv: month, inflation (all items, y/y %), food and core
inflation, naira per US$ (monthly average), and Money Matters' price index (all-items CPI rebuilt
from year-on-year rates, base = latest month = 100).
The health component of NBS CPI is not in this panel (see sources.yaml).
"""
import hashlib
import json
import shutil
import sys

import pandas as pd

from common import PROCESSED, RAW, ROOT, today

SIBLING = ROOT.parent / "naija-money-dashboard" / "data" / "processed"
PREFIX = "money_matters_panel"
COLUMNS = ["month", "inflation", "food_inflation", "core_inflation", "usd_ngn", "price_index"]


def _digest(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    snaps = sorted(RAW.glob(f"{PREFIX}_*.csv"))
    src = SIBLING / "panel.csv"
    if src.exists() and (not snaps or _digest(src) != _digest(snaps[-1])):
        dest = RAW / f"{PREFIX}_{today()}.csv"
        shutil.copyfile(src, dest)
        meta = SIBLING / "meta.json"
        if meta.exists():
            shutil.copyfile(meta, RAW / f"{PREFIX}_meta_{today()}.json")
        print(f"  new snapshot from Money Matters: {dest.name}")
        snaps = sorted(RAW.glob(f"{PREFIX}_*.csv"))
    elif snaps:
        print(f"  using {snaps[-1].name} (unchanged)")
    if not snaps:
        sys.exit("No Money Matters panel found: put panel.csv in data/raw/ as money_matters_panel_<date>.csv")
    p = pd.read_csv(snaps[-1], parse_dates=["month"])[COLUMNS]
    p = p.dropna(subset=["inflation", "usd_ngn"], how="all").sort_values("month")
    metas = sorted(RAW.glob(f"{PREFIX}_meta_*.json"))
    built = json.loads(metas[-1].read_text(encoding="utf-8")).get("built_at_utc", "")[:10] if metas else ""
    p["source_snapshot"] = snaps[-1].name
    p["money_matters_built"] = built
    p.to_csv(PROCESSED / "monthly_prices.csv", index=False)
    print(f"  monthly series: {p.month.min():%Y-%m} to {p.month.max():%Y-%m}, {len(p)} months")


if __name__ == "__main__":
    main()
