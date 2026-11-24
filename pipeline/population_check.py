"""Cross-check GRID3/WorldPop v3.0 state populations against a second published estimate.

Second source: National Population Commission projections for 2023, as published in the NBS
Demographic Bulletin 2023 (data/manual/population_alt.csv, transcribed from Annex 3, page 35).

The two are for different years (GRID3/WorldPop: 2025; NPC: 2023), so states are compared by their
SHARE of the national total, which cancels out overall growth. A state is flagged when its share
differs by more than FLAG_PCT percent (relative). GRID3/WorldPop stays the population used everywhere
else, because it is one consistent model for all 37 states, built from satellite and survey data rather
than projected forward from the 2006 census.

Writes data/processed/population_crosscheck.csv and exports/population_crosscheck_grid3_vs_npc.csv.
"""
import pandas as pd

from common import EXPORTS, MANUAL, PROCESSED, to_official_state

FLAG_PCT = 20


def main() -> pd.DataFrame:
    alt = pd.read_csv(MANUAL / "population_alt.csv")
    alt["state_official"] = to_official_state(alt.state)
    grid = pd.read_csv(PROCESSED / "population_state.csv")[["state", "population_total"]]
    d = grid.merge(alt[["state_official", "population", "reference_year"]].rename(
        columns={"state_official": "state", "population": "population_npc", "reference_year": "npc_year"}),
        on="state", how="outer", validate="one_to_one")
    if d.isna().any().any() or len(d) != 37:
        raise SystemExit("population cross-check: the two sources don't cover the same 37 states")
    d["share_grid3_pct"] = (100 * d.population_total / d.population_total.sum()).round(2)
    d["share_npc_pct"] = (100 * d.population_npc / d.population_npc.sum()).round(2)
    d["share_diff_pct"] = (100 * (d.share_grid3_pct / d.share_npc_pct - 1)).round(0)
    d["flag"] = d.share_diff_pct.abs() > FLAG_PCT
    d["rank_grid3"] = d.population_total.rank(ascending=False, method="min").astype(int)
    d["rank_npc"] = d.population_npc.rank(ascending=False, method="min").astype(int)
    d = d.rename(columns={"population_total": "population_grid3_2025"}).sort_values("share_diff_pct")
    d.to_csv(PROCESSED / "population_crosscheck.csv", index=False)
    EXPORTS.mkdir(exist_ok=True)
    d.to_csv(EXPORTS / "population_crosscheck_grid3_vs_npc.csv", index=False)
    f = d[d.flag]
    print(f"  population cross-check vs NPC {int(d.npc_year.iloc[0])}: {len(f)} states differ by more than "
          f"{FLAG_PCT}% in share of the national total: "
          + ", ".join(f"{r.state} ({r.share_diff_pct:+.0f}%)" for r in f.itertuples()))
    return d


if __name__ == "__main__":
    main()
