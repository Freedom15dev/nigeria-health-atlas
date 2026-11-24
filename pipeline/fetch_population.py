"""GRID3 / WorldPop NGA population v3.0, state totals.

Downloaded by hand (zip of admin-level CSVs). This step checks the file is present
and that the state table is inside it.
"""
import sys
import zipfile

from common import RAW_FILES, sha256

STATE_MEMBER = "NGA_population_v3_0_admin/states_pop_total_scaled.csv"
NATIONAL_MEMBER = "NGA_population_v3_0_admin/national_pop_total_scaled.csv"


def main() -> None:
    p = RAW_FILES["grid3_pop_v3"]
    if not p.exists():
        sys.exit(f"Missing raw population file: {p}")
    names = zipfile.ZipFile(p).namelist()
    for m in (STATE_MEMBER, NATIONAL_MEMBER):
        if m not in names:
            sys.exit(f"{m} not found inside {p.name}")
    print(f"  grid3_pop_v3: {p.name} sha256={sha256(p)[:16]}...")
    print("  note: totals only; no age-sex groups, so population 40+ stays unknown")


if __name__ == "__main__":
    main()
