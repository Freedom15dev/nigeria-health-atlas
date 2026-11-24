"""Summarise the specialist register by state. Shared by the pipeline (load_register.py)
and the app (so a filtered view, e.g. public only, uses exactly the same rules).

Rules: one row per fact; conflicting counts become a range, never an average. State-wide rows
are separate estimates that widen the range, not additions. "0 working" is not a working centre.
"""
import math

import pandas as pd


def capacity_range(df: pd.DataFrame) -> tuple[float, float]:
    """Low-high range of a count for one state.

    Facility-level rows: sum over facilities of each facility's smallest (low) and largest (high)
    reported count. State-wide rows (no facility name) are separate estimates of the same total,
    so they are NOT added to the facility sum; each one widens the range instead."""
    df = df[df["count"].str.strip() != ""].assign(n=lambda d: d["count"].astype(float))
    if df.empty:
        return (float("nan"), float("nan"))
    fac = df[df.facility_name != ""]
    estimates = [(fac.groupby("facility_name").n.min().sum(), fac.groupby("facility_name").n.max().sum())] \
        if len(fac) else []
    estimates += [(v, v) for v in df.loc[df.facility_name == "", "n"]]
    return (min(e[0] for e in estimates), max(e[1] for e in estimates))


# What counts as a machine, a unit and a specialist, by specialty.
MACHINES = {"kidney": ["dialysis machine"], "cancer": ["linac", "cobalt unit"]}
UNITS = {"kidney": ["dialysis centre", "dialysis machine"], "cancer": ["linac", "cobalt unit", "other"]}
SPECIALISTS = {"kidney": "nephrologist", "cancer": "oncologist"}


def machine_range(s: pd.DataFrame, items: list[str]) -> tuple[float, float]:
    """Range per machine type (a linac and a cobalt unit are different machines), then added."""
    parts = [capacity_range(s[s.item == it]) for it in items]
    parts = [p for p in parts if not math.isnan(p[0])]
    if not parts:
        return (math.nan, math.nan)
    return (sum(p[0] for p in parts), sum(p[1] for p in parts))


def summarise_by_state(r: pd.DataFrame, states: list[str], specialty: str = "kidney") -> pd.DataFrame:
    """One row per state in `states`: evidence found or not, working-machine range, gap-type counts."""
    r = r[r.specialty == specialty]
    out = []
    for state in states:
        s = r[r.state == state]
        if s.empty:
            out.append({"state": state, "evidence": "no evidence found", "n_rows": 0})
            continue
        units = s[s.item.isin(UNITS[specialty])]
        public_working = units[(units.ownership == "public") & (units.status == "working")
                               & (units["count"].str.strip() != "0")]  # "0 working" is not a working unit
        public_not = units[(units.ownership == "public") & (units.status == "not working")]
        m_work = machine_range(s[s.status == "working"], MACHINES[specialty])
        m_not = machine_range(s[s.status == "not working"], MACHINES[specialty])
        spec = capacity_range(s[s.item == SPECIALISTS[specialty]])
        gaps = s[s.gap_type != "unknown"].gap_type.value_counts()
        public_unit = "yes" if len(public_working) else "reported not working" if len(public_not) else "unknown"
        row = {
            "state": state, "evidence": "found", "n_rows": len(s),
            "n_facilities": s.loc[s.facility_name != "", "facility_name"].nunique(),
            "public_unit_working": public_unit,
            "machines_working_low": m_work[0], "machines_working_high": m_work[1],
            "machines_not_working_low": m_not[0], "machines_not_working_high": m_not[1],
            "specialists_low": spec[0], "specialists_high": spec[1],
            "gap_equipment": int(gaps.get("equipment", 0)), "gap_workforce": int(gaps.get("workforce", 0)),
            "gap_systems": int(gaps.get("systems", 0)),
            "gap_unknown": int((s.gap_type == "unknown").sum()),
            "earliest_source_date": s.source_date.min(),
            "latest_source_date": s.source_date.max(),
            "source_types": ", ".join(sorted(s.source_type.unique())),
        }
        if specialty == "kidney":  # names used since phase 3
            row["public_dialysis_working"] = public_unit
            row["nephrologists_low"], row["nephrologists_high"] = spec
        out.append(row)
    return pd.DataFrame(out)
