"""Stop the run (exit code 1) if the data breaks any rule.

Rules:
 1. state_panel.csv has exactly 37 rows, one per state code in the lookup.
 2. Pillar input columns have no nulls (a real gap must be written "unknown").
 3. Every panel column is in the dictionary with a source_id and a data date,
    and every source_id is in data/sources.yaml.
 4. Every manual row has source_id, table and printed_page.
 5. Population > 0; percentage columns between 0 and 100.
 6. Sum of state populations within 1% of the national total.
 7. The de-duplication report and the GRID3 vs eHealth Africa comparison exist.
 8. Every register row has a source URL and source date   (active from phase 3).
 9. Payer-mix shares sum to 100%                          (active from phase 4).
11. Every centre-model input has value, low, high, unit, source and worse (phase 4).
10. scorecard.csv and scorecard_stress.csv have 37 rows, no missing scores, every score
    between 0 and 100, and the "screening tool, not investment advice" label on every row.
12. Headline figures (Home page): cards 1-4 each have main figures; every row has a number,
    source, source date, URL and verification note.
13. App inputs exist: the state map joins all 37 states; the monthly series and NBS health CPI
    are present and not empty.
"""
import sys
import zipfile

import pandas as pd
import yaml

from common import CONFIG, EXPORTS, MANUAL, PROCESSED, RAW_FILES, REGISTER, load_sources, load_states
from fetch_population import NATIONAL_MEMBER
from load_manual import check_manual

PILLAR_INPUTS = {
    "need": ["population_total", "bp_ever_told_high_women_pct", "bp_ever_told_high_men_pct",
             "sugar_ever_told_high_women_pct", "sugar_ever_told_high_men_pct"],
    "supply": ["fac_sec_tert_per_100k", "fac_all_per_100k"],
    "ability_to_pay": ["insurance_any_women_pct", "insurance_any_men_pct", "wealth_top2_pct"],
}


def check_panel_rows(panel: pd.DataFrame, states: pd.DataFrame) -> list[str]:
    e = []
    if len(panel) != 37:
        e.append(f"state_panel has {len(panel)} rows, expected 37")
    missing = set(states.state_code) - set(panel.state_code)
    if missing:
        e.append(f"states missing from panel: {sorted(missing)}")
    if panel.state_code.duplicated().any():
        e.append(f"duplicate states: {panel.state_code[panel.state_code.duplicated()].tolist()}")
    return e


def check_pillars(panel: pd.DataFrame) -> list[str]:
    e = []
    for pillar, cols in PILLAR_INPUTS.items():
        for c in cols:
            if c not in panel.columns:
                e.append(f"{pillar}: column {c} missing")
            elif panel[c].isna().any():
                e.append(f"{pillar}: {c} has nulls in {panel.loc[panel[c].isna(), 'state'].tolist()}")
    return e


def check_dictionary(panel: pd.DataFrame, dictionary: pd.DataFrame, sources: dict) -> list[str]:
    e = []
    d = dictionary.set_index("column")
    for c in panel.columns:
        if c not in d.index:
            e.append(f"column {c} not in state_panel_dictionary.csv")
            continue
        sid, date = d.at[c, "source_id"], d.at[c, "data_date"]
        if pd.isna(sid) or not str(sid).strip():
            e.append(f"column {c} has no source_id")
            continue
        if pd.isna(date) or not str(date).strip():
            e.append(f"column {c} has no data date")
        for s in str(sid).split(";"):
            s = s.strip()
            if s != "lookup" and s not in sources:
                e.append(f"column {c}: source_id {s} not in sources.yaml")
    return e


def check_ranges(panel: pd.DataFrame) -> list[str]:
    e = []
    if (panel.population_total <= 0).any():
        e.append("population_total has values <= 0")
    for c in [c for c in panel.columns if c.endswith("_pct")]:
        bad = panel[(panel[c] < 0) | (panel[c] > 100)]
        if len(bad):
            e.append(f"{c} outside 0-100 for {bad.state.tolist()}")
    return e


def check_population_total() -> list[str]:
    pop = pd.read_csv(PROCESSED / "population_state.csv")
    with zipfile.ZipFile(RAW_FILES["grid3_pop_v3"]).open(NATIONAL_MEMBER) as f:
        national = float(pd.read_csv(f)["population"].iloc[0])
    gap = abs(pop.population_total.sum() / national - 1)
    return [f"state populations sum to {gap:.1%} away from national total"] if gap > 0.01 else []


def check_outputs() -> list[str]:
    need = [PROCESSED / "facilities_grid3_dropped_duplicates.csv",
            EXPORTS / "facility_crosscheck_grid3_vs_ehealthafrica.csv",
            PROCESSED / "meta.json"]
    return [f"missing output {p.relative_to(PROCESSED.parents[1])}" for p in need if not p.exists()]


def check_register(path=REGISTER / "specialist_capacity.csv") -> list[str]:
    """Every row: allowed values, an official state name, a source URL, source date and evidence note."""
    if not path.exists():
        return []
    from load_register import check_register_rows, load
    return check_register_rows(load(path))


def check_assumptions(path=CONFIG / "assumptions_kidney.yaml") -> list[str]:
    """Every centre-model input carries value, low, high, unit, source and worse."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        a = yaml.safe_load(f) or {}
    e = []
    for section in ("capacity", "prices", "costs", "fx", "ppp"):
        for name, spec in (a.get(section) or {}).items():
            missing = [k for k in ("value", "low", "high", "unit", "source", "worse") if k not in spec]
            if missing:
                e.append(f"assumptions {section}.{name} missing {missing}")
            elif not str(spec["source"]).strip():
                e.append(f"assumptions {section}.{name} has an empty source")
    return e


def check_payer_mix(path=CONFIG / "assumptions_kidney.yaml") -> list[str]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        a = yaml.safe_load(f) or {}
    mix = a.get("payer_mix", {})
    for scenario in ("value", "low", "high"):
        shares = [v[scenario] for v in mix.values() if isinstance(v, dict) and scenario in v]
        if shares and abs(sum(shares) - 1) > 1e-6:
            return [f"payer_mix ({scenario}) sums to {sum(shares):.4f}, not 1.0"]
    return []


def check_scorecard() -> list[str]:
    e = []
    for name in ("scorecard.csv", "scorecard_stress.csv", "scorecard_sensitivity_need.csv"):
        path = PROCESSED / name
        if not path.exists():
            e.append(f"missing {name}")
            continue
        df = pd.read_csv(path)
        if len(df) != 37:
            e.append(f"{name} has {len(df)} rows, expected 37")
        if "label" not in df.columns or df.label.isna().any():
            e.append(f"{name}: every row needs the screening-tool label")
        for c in [c for c in df.columns if c.startswith("score_")]:
            if df[c].isna().any():
                e.append(f"{name}: {c} has missing values")
            elif ((df[c] < 0) | (df[c] > 100)).any():
                e.append(f"{name}: {c} outside 0-100")
    return e


def check_headline_figures(path=MANUAL / "headline_figures.csv") -> list[str]:
    if not path.exists():
        return [f"{path.name} missing"]
    h = pd.read_csv(path, dtype=str, keep_default_na=False)
    e = []
    if sorted(h.loc[h.role == "main", "card"].unique()) != ["1", "2", "3", "4"]:
        e.append("headline_figures: each of cards 1-4 needs at least one 'main' row")
    for col in ("figure", "source", "source_date", "url", "verification_note"):
        if (h[col].str.strip() == "").any():
            e.append(f"headline_figures: empty {col} in rows {list(h.index[h[col].str.strip() == ''])}")
    if pd.to_numeric(h.figure, errors="coerce").isna().any():
        e.append("headline_figures: non-numeric figure")
    if not h.role.isin(["main", "context"]).all():
        e.append("headline_figures: role must be main or context")
    return e


def check_app_inputs() -> list[str]:
    import json
    e = []
    geo = PROCESSED / "nga_states.geojson"
    if not geo.exists():
        return ["nga_states.geojson missing"]
    names = {f["properties"]["state"] for f in json.loads(geo.read_text(encoding="utf-8"))["features"]}
    if names != set(load_states().state):
        e.append(f"state map does not match the lookup: {sorted(names ^ set(load_states().state))}")
    for name in ("monthly_prices.csv", "nbs_cpi_health.csv", "facility_counts.csv", "register_kidney_rows.csv",
                 "headline_figures.csv", "sources.csv", "states.csv"):
        if not (PROCESSED / name).exists() or pd.read_csv(PROCESSED / name).empty:
            e.append(f"{name} missing or empty")
    return e


def run_all_checks() -> list[str]:
    panel = pd.read_csv(PROCESSED / "state_panel.csv")
    dictionary = pd.read_csv(PROCESSED / "state_panel_dictionary.csv")
    sources = load_sources()
    errors = []
    errors += check_panel_rows(panel, load_states())
    errors += check_pillars(panel)
    errors += check_dictionary(panel, dictionary, sources)
    for f in sorted(MANUAL.glob("*.csv")):
        if f.name == "headline_figures.csv":
            continue  # different layout: checked by check_headline_figures
        errors += check_manual(pd.read_csv(f), f.name, sources)
    errors += check_ranges(panel)
    errors += check_population_total()
    errors += check_outputs()
    errors += check_register()
    errors += check_payer_mix()
    errors += check_assumptions()
    errors += check_scorecard()
    errors += check_headline_figures()
    errors += check_app_inputs()
    return errors


def main() -> None:
    errors = run_all_checks()
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("  validation passed: 37 states, pillar inputs complete, every column sourced and dated, "
          "scorecard complete")


if __name__ == "__main__":
    main()
