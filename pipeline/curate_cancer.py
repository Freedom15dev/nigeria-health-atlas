"""One-off (phase 6): add the cancer (radiotherapy) rows to data/register/specialist_capacity.csv.

Research files (raw output of the source search, one JSON object per fact with URL, date and quote):
  data/register/research/cancer_north.json, cancer_south.json, cancer_national.json -> the register
  data/register/research/cancer_costs.json -> data/register/cancer_cost_evidence.csv (prices, costs,
                                              throughput: evidence for the centre model, not capacity)

Curation rules (every change is visible here, and noted in the row as "[Curation: ...]"):
  1. State values outside the lookup: "national" -> "National"; a regional figure ("regional: northern
     Nigeria") is stored under "National" with a note saying it covers the North only.
  2. Remove exact duplicates (same state, facility, item, count, status and URL): the same national
     figure was found by two searches.
  3. Kidney rows are left exactly as they are; existing cancer rows are replaced.

Not part of run_all.py. Re-run after adding research files.
"""
import json

import pandas as pd

from common import REGISTER
from load_register import COLUMNS, REGISTER_FILE, check_register_rows

RESEARCH = REGISTER / "research"
CAPACITY_FILES = ["cancer_north.json", "cancer_south.json", "cancer_national.json"]
COST_FILE = REGISTER / "cancer_cost_evidence.csv"


def load(name: str) -> pd.DataFrame:
    rows = json.loads((RESEARCH / name).read_text(encoding="utf-8"))
    return pd.DataFrame(rows, dtype=str).fillna("")[COLUMNS]


def curate(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d.loc[d.state.str.lower() == "national", "state"] = "National"
    regional = d.state.str.startswith("regional")
    d.loc[regional, "evidence_note"] += (" [Curation: a regional figure (" + d.loc[regional, "state"].str.replace(
        "regional: ", "") + "), stored under National]")
    d.loc[regional, "state"] = "National"
    before = len(d)
    d = d.drop_duplicates(["state", "facility_name", "item", "count", "status", "source_url"])
    print(f"  cancer: {before} research rows, {before - len(d)} exact duplicates removed, {len(d)} kept")
    return d


def main() -> None:
    cancer = curate(pd.concat([load(f) for f in CAPACITY_FILES], ignore_index=True))
    costs = load("cancer_costs.json")
    errors = check_register_rows(pd.concat([cancer, costs]))
    if errors:
        raise SystemExit("Cancer rows break register rules:\n  " + "\n  ".join(errors[:30]))
    reg = pd.read_csv(REGISTER_FILE, dtype=str, keep_default_na=False)
    kidney = reg[reg.specialty != "cancer"]
    out = pd.concat([kidney, cancer.sort_values(["state", "facility_name", "item", "source_date"])],
                    ignore_index=True)
    out.to_csv(REGISTER_FILE, index=False)
    costs.to_csv(COST_FILE, index=False)
    print(f"  register: {len(kidney)} kidney rows unchanged + {len(cancer)} cancer rows; "
          f"{len(costs)} cost rows -> {COST_FILE.name}")


if __name__ == "__main__":
    main()
