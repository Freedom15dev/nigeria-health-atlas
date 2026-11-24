"""Clean each source into tidy tables in data/processed/.

- State names go through the one lookup (data trap 1).
- Facility levels go through data/lookups/facility_levels.csv (data trap 2).
- GRID3 duplicates: same state + LGA + normalised name AND under 100 m apart
  (data trap 3). eHealth Africa has no coordinates, so it is not de-duplicated;
  its possible duplicates (same name + LGA) are only counted.
"""
import json
import re
import sqlite3
import sys
import zipfile

import numpy as np
import pandas as pd

from common import LOOKUPS, PROCESSED, RAW_FILES, latest_raw, to_official_state
from fetch_population import NATIONAL_MEMBER, STATE_MEMBER

DEDUP_METRES = 100


# ---------- helpers ----------

def norm_name(s: pd.Series) -> pd.Series:
    """Letters and digits only, so 'P.H.C', 'P H C' and 'PHC' match."""
    return s.fillna("").str.lower().str.replace(r"[^a-z0-9]", "", regex=True)


def haversine_m(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6_371_000 * 2 * np.arcsin(np.sqrt(a))


def dedupe_by_distance(df: pd.DataFrame, metres: float = DEDUP_METRES) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drop rows that share state, LGA and normalised name with an earlier row
    AND lie within `metres` of it. Returns (kept, dropped)."""
    df = df.copy()
    df["_key"] = df["state"] + "|" + df["lga"].fillna("").str.lower() + "|" + norm_name(df["facility_name"])
    drop_idx = []
    for _, g in df[df.duplicated("_key", keep=False)].groupby("_key"):
        kept = []
        for idx, row in g.iterrows():
            if any(haversine_m(row.latitude, row.longitude, df.at[k, "latitude"], df.at[k, "longitude"]) < metres
                   for k in kept):
                drop_idx.append(idx)
            else:
                kept.append(idx)
    dropped = df.loc[drop_idx].drop(columns="_key")
    return df.drop(index=drop_idx).drop(columns="_key"), dropped


def map_levels(raw: pd.Series, source_id: str, field: str) -> pd.Series:
    lk = pd.read_csv(LOOKUPS / "facility_levels.csv")
    lk = lk[(lk.source_id == source_id) & (lk.field == field)]
    m = dict(zip(lk.raw_value, lk.level))
    out = raw.fillna("Unknown").map(m)
    missing = sorted(set(raw[out.isna()].astype(str)))
    if missing:
        sys.exit(f"Facility level values not in facility_levels.csv for {source_id}.{field}: {missing}")
    return out


# ---------- sources ----------

def clean_grid3() -> dict:
    con = sqlite3.connect(f"file:{RAW_FILES['grid3_hf_v2'].as_posix()}?mode=ro", uri=True)
    g = pd.read_sql('select * from "NGA_health_facilities_v2_0"', con).drop(columns=["geom"])
    con.close()
    g["state"] = to_official_state(g["state"])
    g["level"] = map_levels(g["facility_level"], "grid3_hf_v2", "facility_level")
    g["ownership"] = g["ownership"].str.lower()
    keep = ["globalid", "state", "lga", "ward", "facility_name", "level", "facility_level_option",
            "ownership", "ownership_type", "latitude", "longitude", "geocoordinates_source", "last_updated"]
    g = g[keep]
    n_before = len(g)
    g, dropped = dedupe_by_distance(g)
    g.to_csv(PROCESSED / "facilities_grid3.csv", index=False)
    dropped.to_csv(PROCESSED / "facilities_grid3_dropped_duplicates.csv", index=False)
    print(f"  GRID3 v2.0: {n_before} rows, dropped {len(dropped)} duplicates "
          f"(same name + LGA, < {DEDUP_METRES} m), kept {len(g)}")
    return {"rows_in": n_before, "duplicates_dropped": len(dropped), "rows_out": len(g)}


def clean_ehealthafrica() -> dict:
    e = pd.read_csv(RAW_FILES["ehealthafrica_hf"])
    e["state"] = to_official_state(e["state_name"])
    e["level"] = map_levels(e["type"], "ehealthafrica_hf", "type")
    e = e.rename(columns={"name": "facility_name", "lga_name": "lga"})
    possible_dups = int(e.assign(_n=norm_name(e.facility_name), _l=e.lga.str.lower())
                        .duplicated(["state", "_l", "_n"]).sum())
    e = e[["global_id", "state", "lga", "facility_name", "level", "type", "category",
           "functional_status", "timestamp"]]
    e.to_csv(PROCESSED / "facilities_ehealthafrica.csv", index=False)
    print(f"  eHealth Africa: {len(e)} rows; {possible_dups} share name + LGA "
          "(not dropped: no coordinates to confirm)")
    return {"rows": len(e), "possible_duplicates_not_dropped": possible_dups}


def clean_population() -> dict:
    z = zipfile.ZipFile(RAW_FILES["grid3_pop_v3"])
    with z.open(STATE_MEMBER) as f:
        p = pd.read_csv(f)
    with z.open(NATIONAL_MEMBER) as f:
        national = float(pd.read_csv(f)["population"].iloc[0])
    p["state"] = to_official_state(p["statename"])
    p = p.rename(columns={"statename": "state_as_published", "population": "population_total"})
    p["population_40plus"] = "unknown"  # no age-sex groups in this file
    p.to_csv(PROCESSED / "population_state.csv", index=False)
    total = p["population_total"].sum()
    print(f"  Population: {len(p)} states, sum {total:,.0f} vs national {national:,.0f} "
          f"({(total / national - 1) * 100:+.2f}%)")
    return {"states": len(p), "sum_of_states": total, "national_total": national}


def clean_dhs() -> dict:
    path = latest_raw("dhs_NG2024DHS_state")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    d = pd.DataFrame(raw["payload"]["Data"])
    d = d[d["LevelRank"] == 2].copy()  # 2 = state rows (1 = zones)
    d["state"] = to_official_state(d["CharacteristicLabel"].str.lstrip("."))
    d["source_id"] = "ndhs2024_api"
    d["raw_file"] = path.name
    d["pulled"] = raw["_pulled"]
    d = d[["state", "IndicatorId", "Indicator", "Value", "DenominatorWeighted",
           "DenominatorUnweighted", "CILow", "CIHigh", "source_id", "raw_file", "pulled"]]
    d.to_csv(PROCESSED / "dhs_state_long.csv", index=False)
    print(f"  DHS API: {d.IndicatorId.nunique()} indicators x {d.state.nunique()} states from {path.name}")
    return {"raw_file": path.name, "indicators": int(d.IndicatorId.nunique()), "states": int(d.state.nunique())}


def clean_wdi() -> dict:
    path = latest_raw("wdi_nga")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    rows = [{"indicator_id": k, **r} for k, v in raw["payload"].items() for r in v]
    w = pd.DataFrame(rows).dropna(subset=["value"])
    w["source_id"], w["raw_file"], w["pulled"] = "wdi", path.name, raw["_pulled"]
    w.to_csv(PROCESSED / "wdi_nga.csv", index=False)
    latest = w.sort_values("year").groupby("indicator_id").tail(1)
    for _, r in latest.iterrows():
        print(f"  WDI {r.indicator_id}: latest {r.year} = {r.value:.1f}")
    return {"raw_file": path.name}


def main() -> dict:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    return {
        "grid3": clean_grid3(),
        "ehealthafrica": clean_ehealthafrica(),
        "population": clean_population(),
        "dhs": clean_dhs(),
        "wdi": clean_wdi(),
    }


if __name__ == "__main__":
    main()
