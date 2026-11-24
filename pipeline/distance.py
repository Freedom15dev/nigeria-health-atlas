"""How far is the nearest working dialysis unit? (story beat 1, "The patient")

For every LGA: straight-line distance from the LGA's approximate centre to the nearest dialysis unit
that the register names as working. Then, per state, the share of people living beyond 50, 100 and
200 km, weighted by LGA population.

Inputs
  data/register/specialist_capacity.csv      named kidney units with a "working" row (not "0 working")
  data/lookups/dialysis_unit_locations.csv   each unit's coordinates (GRID3 match, proxy or unverified)
  data/processed/facilities_grid3.csv        LGA centre = median latitude/longitude of the LGA's facilities
  GRID3/WorldPop v3.0 LGA population         population weights

Writes data/processed/lga_dialysis_distance.csv and state_dialysis_distance.csv.

Read the result as an UPPER BOUND on distance: the register is a floor (sources name some working
units, not all), roads are longer than straight lines, and an LGA centre is not where everyone lives.
"""
import difflib
import math
import zipfile

import numpy as np
import pandas as pd

from common import LOOKUPS, PROCESSED, RAW_FILES, REGISTER, load_states, to_official_state

LGA_MEMBER = "NGA_population_v3_0_admin/lga_pop_total_scaled.csv"
BANDS = [50, 100, 200]


def _key(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().str.replace(r"[^a-z]", "", regex=True)


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def working_units() -> pd.DataFrame:
    r = pd.read_csv(REGISTER / "specialist_capacity.csv", dtype=str, keep_default_na=False)
    k = r[(r.specialty == "kidney") & (r.facility_name != "") & (r.status == "working")
          & r.item.isin(["dialysis centre", "dialysis machine"]) & (r["count"].str.strip() != "0")]
    named = k[["state", "facility_name", "ownership"]].drop_duplicates(["state", "facility_name"])
    loc = pd.read_csv(LOOKUPS / "dialysis_unit_locations.csv", dtype={"latitude": float, "longitude": float})
    u = named.merge(loc, on=["state", "facility_name"], how="left")
    missing = u[u.latitude.isna()]
    if len(missing):
        raise SystemExit(f"Working units with no location in dialysis_unit_locations.csv: "
                         f"{missing.facility_name.tolist()}")
    return u


def lga_centres() -> pd.DataFrame:
    """LGA population (GRID3/WorldPop) joined to an approximate centre from GRID3 facility locations."""
    with zipfile.ZipFile(RAW_FILES["grid3_pop_v3"]) as z:
        pop = pd.read_csv(z.open(LGA_MEMBER))
    pop["state"] = to_official_state(pop.statename)
    f = pd.read_csv(PROCESSED / "facilities_grid3.csv", usecols=["state", "lga", "latitude", "longitude"])
    centres = f.groupby(["state", "lga"])[["latitude", "longitude"]].median().reset_index()
    centres["k"] = _key(centres.lga)
    pop["k"] = _key(pop.lganame)
    # exact name match first, then the closest spelling in the same state (e.g. "Yenegoa" / "Yenagoa")
    out = []
    for _, p in pop.iterrows():
        c = centres[centres.state == p.state]
        hit = c[c.k == p.k]
        how = "exact"
        if hit.empty:
            close = difflib.get_close_matches(p.k, c.k.tolist(), n=1, cutoff=0.7)
            hit, how = (c[c.k == close[0]], "closest spelling") if close else (hit, "no match")
        row = {"state": p.state, "lga": p.lganame, "population": p.population, "match": how,
               "latitude": math.nan, "longitude": math.nan}
        if len(hit):
            row.update(latitude=hit.latitude.iloc[0], longitude=hit.longitude.iloc[0], grid3_lga=hit.lga.iloc[0])
        out.append(row)
    return pd.DataFrame(out)


def main() -> None:
    units = working_units()
    lga = lga_centres()
    have = lga.dropna(subset=["latitude"]).copy()
    d = haversine_km(have.latitude.values[:, None], have.longitude.values[:, None],
                     units.latitude.values[None, :], units.longitude.values[None, :])
    i = d.argmin(axis=1)
    have["nearest_unit"] = units.facility_name.values[i]
    have["nearest_unit_state"] = units.state.values[i]
    have["km_straight_line"] = d.min(axis=1).round(0)
    lga = lga.merge(have[["state", "lga", "nearest_unit", "nearest_unit_state", "km_straight_line"]],
                    on=["state", "lga"], how="left")
    lga.to_csv(PROCESSED / "lga_dialysis_distance.csv", index=False)

    rows = []
    for st in load_states().state:
        s = lga[(lga.state == st) & lga.km_straight_line.notna()]
        pop = s.population.sum()
        row = {"state": st, "lgas": int((lga.state == st).sum()), "lgas_with_distance": len(s),
               "population_covered": pop,
               "median_km_population_weighted": _weighted_median(s.km_straight_line, s.population),
               "max_km": s.km_straight_line.max(),
               "working_units_in_state": int((units.state == st).sum())}
        for b in BANDS:
            row[f"share_beyond_{b}km_pct"] = round(100 * s.loc[s.km_straight_line > b, "population"].sum() / pop, 1)
        rows.append(row)
    sd = pd.DataFrame(rows)
    sd["label"] = "Straight-line distance to the nearest dialysis unit the register names as working: an upper bound"
    sd.to_csv(PROCESSED / "state_dialysis_distance.csv", index=False)
    nat = lga.dropna(subset=["km_straight_line"])
    share = 100 * nat.loc[nat.km_straight_line > 100, "population"].sum() / nat.population.sum()
    print(f"  {len(units)} working units located; {len(nat)} of {len(lga)} LGAs measured "
          f"({lga.match.value_counts().to_dict()}); {share:.0f}% of people live more than 100 km "
          f"(straight line) from a unit the register names as working")


def _weighted_median(values: pd.Series, weights: pd.Series) -> float:
    if values.empty:
        return math.nan
    o = values.argsort()
    v, w = values.values[o], weights.values[o]
    return float(v[np.searchsorted(np.cumsum(w), w.sum() / 2)])


if __name__ == "__main__":
    main()
