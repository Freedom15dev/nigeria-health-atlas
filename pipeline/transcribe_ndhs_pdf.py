"""One-off: transcribe NDHS 2024 state rows from the FR395 PDF into
data/manual/ndhs2024_state.csv, with the table and page number on every row.

Not part of run_all.py (the PDF doesn't change). Re-run only if the PDF is replaced.
Needs pypdf (pipeline-only dependency).

Tables (PDF page = printed page + 44):
  19.1.1 Blood pressure diagnosis and treatment: Women  (printed p.587)
  19.1.2 Blood pressure diagnosis and treatment: Men    (printed p.589)
  19.2.1 Blood sugar diagnosis and treatment: Women     (printed p.591)
  19.2.2 Blood sugar diagnosis and treatment: Men       (printed p.593)

Only the first three columns are kept per state: "ever measured", "ever told",
and the weighted number of respondents. The treatment columns are mostly
suppressed (*) or based on 25-49 cases at state level, so they are left out.
These are self-reported, ages 15-49, not measured prevalence.
"""
import re
import sys

import pandas as pd
from pypdf import PdfReader

from common import MANUAL, RAW_FILES, to_official_state

TABLES = [
    # (table, pdf_page, sex, topic)
    ("19.1.1", 631, "women", "blood_pressure"),
    ("19.1.2", 633, "men", "blood_pressure"),
    ("19.2.1", 635, "women", "blood_sugar"),
    ("19.2.2", 637, "men", "blood_sugar"),
]
ROW = re.compile(r"^\s*([A-Za-z][A-Za-z \-]*?)\s+(\d+\.\d)\s+(\d+\.\d)\s+([\d,]+)\s")
PRINTED_PAGE = re.compile(r"(?:•\s*(\d{3})\s*$)|(?:^\s*(\d{3})\s*•)", re.M)


def parse_page(text: str, table: str) -> tuple[int, list[tuple]]:
    if f"Table {table} " not in text:
        raise ValueError(f"Table {table} not found on expected page")
    m = PRINTED_PAGE.search(text.splitlines()[0] + "\n")
    printed = int(m.group(1) or m.group(2))
    body = text.split("\nState", 1)[1].split("Continued", 1)[0]
    rows = [ROW.match(line).groups() for line in body.splitlines() if ROW.match(line)]
    return printed, rows


def main() -> None:
    reader = PdfReader(RAW_FILES["ndhs2024_fr395"])
    records = []
    for table, pdf_page, sex, topic in TABLES:
        printed, rows = parse_page(reader.pages[pdf_page - 1].extract_text(), table)
        if len(rows) != 37:
            sys.exit(f"Table {table}: expected 37 state rows, found {len(rows)}")
        for name, measured, told, n in rows:
            base = dict(source_id="ndhs2024_fr395", table=table, printed_page=printed,
                        pdf_page=pdf_page, state_as_printed=name.strip(), sex=sex,
                        age_range="15-49", n_weighted=int(n.replace(",", "")))
            records.append({**base, "indicator": f"{topic}_ever_measured_pct", "value": float(measured)})
            records.append({**base, "indicator": f"{topic}_ever_told_high_pct", "value": float(told)})
    df = pd.DataFrame(records)
    df.insert(0, "state", to_official_state(df["state_as_printed"]))
    df["note"] = "self-reported; not measured prevalence"
    MANUAL.mkdir(parents=True, exist_ok=True)
    out = MANUAL / "ndhs2024_state.csv"
    df.to_csv(out, index=False)
    print(f"  wrote {out.relative_to(MANUAL.parents[1])} ({len(df)} rows)")


if __name__ == "__main__":
    main()
