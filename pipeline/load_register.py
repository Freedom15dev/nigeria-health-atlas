"""Load the hand-built specialist capacity register and summarise it by state.

data/register/specialist_capacity.csv has one row per fact from one source. When two sources
disagree, both rows stay: nothing is averaged. The state summary therefore shows a RANGE:
  low  = for each facility, the smallest reported count; summed over facilities
  high = for each facility, the largest reported count; summed over facilities
States with no rows are "no evidence found", which is different from "no capacity".

Writes data/processed/register_kidney_by_state.csv (37 rows) and register_kidney_national.csv.
"""
import sys

import pandas as pd

from common import PROCESSED, REGISTER, ROOT, load_states

sys.path.insert(0, str(ROOT / "src"))
from register_summary import capacity_range as _range  # noqa: E402,F401
from register_summary import summarise_by_state as _summarise  # noqa: E402

REGISTER_FILE = REGISTER / "specialist_capacity.csv"
COLUMNS = ["specialty", "state", "facility_name", "ownership", "item", "count", "status", "gap_type",
           "evidence_note", "source_url", "source_type", "source_date", "date_accessed"]
ALLOWED = {
    "specialty": {"kidney", "cancer"},
    "ownership": {"public", "private", "mixed", "unknown"},
    "item": {"dialysis machine", "dialysis centre", "nephrologist", "linac", "cobalt unit", "oncologist", "other"},
    "status": {"working", "not working", "unknown"},
    "gap_type": {"equipment", "workforce", "systems", "unknown"},
    "source_type": {"peer-reviewed", "government", "professional body", "news"},
}
NATIONAL = "National"


def load(path=REGISTER_FILE) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def check_register_rows(r: pd.DataFrame) -> list[str]:
    e = []
    missing = [c for c in COLUMNS if c not in r.columns]
    if missing:
        return [f"register: missing columns {missing}"]
    states = set(load_states().state) | {NATIONAL}
    for i, row in r.iterrows():
        tag = f"register row {i + 2}"  # +2: header line and 1-based numbering, matches the CSV line
        for col, allowed in ALLOWED.items():
            if row[col] not in allowed:
                e.append(f"{tag}: {col} = '{row[col]}' not allowed")
        if row["state"] not in states:
            e.append(f"{tag}: state '{row['state']}' not an official name")
        for col in ("source_url", "source_date", "date_accessed", "evidence_note"):
            if not row[col].strip():
                e.append(f"{tag}: no {col}")
        if row["source_url"] and not row["source_url"].startswith("http"):
            e.append(f"{tag}: source_url is not a web address")
        if row["count"].strip():
            try:
                float(row["count"])
            except ValueError:
                e.append(f"{tag}: count '{row['count']}' is not a number")
    return e


def summarise_by_state(r: pd.DataFrame, specialty: str = "kidney") -> pd.DataFrame:
    return _summarise(r, list(load_states().state), specialty)


def main() -> None:
    if not REGISTER_FILE.exists():
        print("  no register yet (phase 3)")
        return
    r = load()
    errors = check_register_rows(r)
    if errors:
        sys.exit("Register problems:\n  " + "\n  ".join(errors[:30]))
    by_state = summarise_by_state(r)
    by_state.to_csv(PROCESSED / "register_kidney_by_state.csv", index=False)
    r[(r.specialty == "kidney") & (r.state == NATIONAL)].to_csv(PROCESSED / "register_kidney_national.csv", index=False)
    k = r[r.specialty == "kidney"]
    print(f"  register: {len(k)} kidney rows; {int((by_state.evidence == 'found').sum())} of 37 states have evidence; "
          f"gap_type unknown in {int((k.gap_type == 'unknown').sum())} rows")


if __name__ == "__main__":
    main()
