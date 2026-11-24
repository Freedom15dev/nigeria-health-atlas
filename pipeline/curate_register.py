"""One-off: build data/register/specialist_capacity.csv from the research files.

The research files in data/register/research/*.json are the raw output of the source search
(one JSON object per fact, each with a URL, date and quote). This script applies a small, written
set of curation rules, so every change between research and register is visible here:

  1. Drop rows with no usable source date (the register requires one).
  2. Move price and payment-share rows (cost per session, % paid out-of-pocket) to
     data/register/kidney_cost_evidence.csv. They are evidence for the phase 4 centre model,
     not capacity facts. Payment problems stated as a barrier stay in the register as "systems".
  3. Give each facility one name (FACILITY_NAMES), so the same hospital isn't counted twice.
  4. Fix the few rows where the recorded status said more than the quote (STATUS_FIXES).
     Each fix is noted in the row's evidence_note as "[Curation: ...]".
  5. Remove exact duplicates (same state, facility, item, count, status and URL).

Not part of run_all.py. Re-run after adding research files.
"""
import json
import re

import pandas as pd

from common import REGISTER
from load_register import COLUMNS, REGISTER_FILE, check_register_rows

RESEARCH = REGISTER / "research"
COST_FILE = REGISTER / "kidney_cost_evidence.csv"

# Same facility, different spellings in different sources -> one name.
FACILITY_NAMES = {
    "University of Benin Teaching Hospital (UBTH)": "University of Benin Teaching Hospital",
    "Federal Medical Centre, Ebute-Metta": "Federal Medical Centre, Ebute Metta",
    "University College Hospital (UCH), Ibadan": "University College Hospital, Ibadan",
    "Abubakar Tafawa Balewa University Teaching Hospital (ATBUTH)": "Abubakar Tafawa Balewa University Teaching Hospital",
    "University of Maiduguri Teaching Hospital (UMTH)": "University of Maiduguri Teaching Hospital",
    "University of Maiduguri Teaching Hospital (UMTH), Kidney Centre": "University of Maiduguri Teaching Hospital",
    "Sir Yahaya Memorial Specialist Hospital, Birnin Kebbi": "Sir Yahaya Memorial Hospital, Birnin Kebbi",
    "Yariman Bakura Specialist Hospital, Gusau": "Ahmad Sani Yariman Bakura Specialist Hospital, Gusau",
    "Fatima Abubakar Renal Dialysis Center, State Specialist Hospital Hadejia": "Fatima Abubakar Dialysis Centre, Hadejia",
    "Yola Specialist Hospital (Adamawa State Specialist Hospital)": "Adamawa State Specialist Hospital, Yola",
    "Bauchi Specialist Hospital": "Bauchi State Specialist Hospital",
    "Federal Teaching Hospital, Ado-Ekiti (as written in source; CMD Prof. Adekunle Ajayi - likely Federal Teaching Hospital Ido-Ekiti, verify)":
        "Federal Teaching Hospital, Ekiti (source says Ado-Ekiti; likely Ido-Ekiti, unverified)",
    "Abubakar Tafawa Balewa University Teaching Hospital (ATBUTH), Renal Centre": "Abubakar Tafawa Balewa University Teaching Hospital",
}

# (state, facility substring, quote substring) -> (field, new value, note)
STATUS_FIXES = [
    ("Abia", "", "operates irregularly", "status", "unknown",
     "status set to unknown: the source says 'operates irregularly', not 'not working'"),
    ("Cross River", "Ogoja", "absence of a functional dialysis referral centre", "status", "working",
     "recorded as 0 working centres in northern Cross River (the source says there is no functional one)"),
]

COST_PATTERN = re.compile(r"(per session|session cost|cost per|average cost|average cycle|out-of-pocket payment|"
                          r"N\d[\d,]* per|N\d[\d,]* to N\d|from N\d)", re.I)


def is_cost_row(r: pd.Series) -> bool:
    """Price/payment-share facts with no stated capacity problem."""
    return r["item"] == "other" and r["gap_type"] == "unknown" and bool(COST_PATTERN.search(r["evidence_note"]))


def main() -> None:
    files = sorted(RESEARCH.glob("*.json"))
    raw = []
    for f in files:
        for obj in json.loads(f.read_text(encoding="utf-8-sig")):
            raw.append({**{k: "" if obj.get(k) is None else str(obj.get(k)) for k in COLUMNS}, "_file": f.name})
    df = pd.DataFrame(raw)
    log = {"research rows": len(df)}

    dated = df.source_date.str.match(r"^\d{4}(-\d{2}){0,2}$")
    log["dropped: no usable date"] = int((~dated).sum())
    df = df[dated].copy()

    df["facility_name"] = df.facility_name.replace(FACILITY_NAMES)

    for state, fac, quote, field, value, note in STATUS_FIXES:
        m = (df.state == state) & df.facility_name.str.contains(fac, regex=False) & \
            df.evidence_note.str.contains(quote, regex=False)
        if m.sum() != 1:
            raise SystemExit(f"status fix matched {m.sum()} rows: {state} / {quote}")
        df.loc[m, field] = value
        df.loc[m, "evidence_note"] += f" [Curation: {note}]"
    log["status fixes"] = len(STATUS_FIXES)

    cost = df.apply(is_cost_row, axis=1)
    df.loc[cost, COLUMNS].to_csv(COST_FILE, index=False)
    log["moved to cost evidence"] = int(cost.sum())
    df = df[~cost]

    key = ["state", "facility_name", "item", "count", "status", "source_url"]
    log["exact duplicates removed"] = int(df.duplicated(key).sum())
    df = df.drop_duplicates(key)

    df = df.sort_values(["specialty", "state", "facility_name", "item", "source_date"])[COLUMNS]
    errors = check_register_rows(df.reset_index(drop=True))
    if errors:
        raise SystemExit("Register problems:\n  " + "\n  ".join(errors))
    df.to_csv(REGISTER_FILE, index=False)
    log["register rows"] = len(df)
    for k, v in log.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
