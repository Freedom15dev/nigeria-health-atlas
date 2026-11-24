"""Small, ready-to-read tables for the Streamlit app (Phase 5).

The app never reads raw files, calls an API or does heavy work: everything it shows comes
from data/processed/. This step writes:
  facility_counts.csv      GRID3 facilities (after de-duplication) by state x level x ownership
  register_<specialty>_rows.csv  the full register per specialty (one row per fact, with source and date)
  headline_figures.csv     the four Home page figures (from data/manual/headline_figures.csv)
  sources.csv              data/sources.yaml as a table (Under the hood page)
  states.csv               the states lookup: official name, display name, code, zone
"""
import pandas as pd

from common import LOOKUPS, MANUAL, PROCESSED, REGISTER, load_sources

LEVELS = ["primary", "secondary", "tertiary", "unknown"]
OWNERSHIP = ["public", "private", "unknown"]
HEADLINE_COLUMNS = ["card", "role", "figure", "unit", "qualifier", "label", "line", "source_short", "source", "source_date", "url",
                    "verification_note"]


def facility_counts() -> pd.DataFrame:
    f = pd.read_csv(PROCESSED / "facilities_grid3.csv", usecols=["state", "level", "ownership"])
    states = pd.read_csv(LOOKUPS / "states.csv", dtype=str, keep_default_na=False)[["state", "zone"]]
    grid = pd.MultiIndex.from_product([states.state, LEVELS, OWNERSHIP], names=["state", "level", "ownership"])
    n = f.groupby(["state", "level", "ownership"]).size().reindex(grid, fill_value=0).rename("facilities")
    return n.reset_index().merge(states, on="state")


def sources_table() -> pd.DataFrame:
    rows = []
    for key, s in load_sources().items():
        fields = s.get("fields_used", "")
        rows.append({"key": key, "name": s.get("name", ""), "publisher": s.get("publisher", ""),
                     "url": s.get("url", ""), "date_accessed": str(s.get("date_accessed", "")),
                     "data_as_of": str(s.get("data_as_of", "")), "licence": s.get("licence", ""),
                     "fields_used": ", ".join(map(str, fields)) if isinstance(fields, list) else str(fields),
                     "notes": " ".join(str(s.get("notes", "")).split())})
    return pd.DataFrame(rows)


def main() -> None:
    fc = facility_counts()
    fc.to_csv(PROCESSED / "facility_counts.csv", index=False)
    reg = pd.read_csv(REGISTER / "specialist_capacity.csv", dtype=str, keep_default_na=False)
    for specialty in ("kidney", "cancer"):
        reg[reg.specialty == specialty].to_csv(PROCESSED / f"register_{specialty}_rows.csv", index=False)
    hf = pd.read_csv(MANUAL / "headline_figures.csv", dtype=str, keep_default_na=False)
    hf[HEADLINE_COLUMNS].to_csv(PROCESSED / "headline_figures.csv", index=False)
    sources_table().to_csv(PROCESSED / "sources.csv", index=False)
    pd.read_csv(LOOKUPS / "states.csv", dtype=str, keep_default_na=False)[
        ["state", "display_name", "state_code", "zone"]].to_csv(PROCESSED / "states.csv", index=False)
    print(f"  facility_counts: {fc.facilities.sum():,} facilities in {fc.state.nunique()} states; "
          f"register rows: {len(reg)}; headline cards: {len(hf)}")


if __name__ == "__main__":
    main()
