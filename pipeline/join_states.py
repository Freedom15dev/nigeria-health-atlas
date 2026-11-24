"""Join everything by state into data/processed/state_panel.csv (37 rows).

Also writes state_panel_dictionary.csv: one row per column with its meaning,
unit, source_id, data date and how it was derived. This is how every number in
the panel traces back to a source.
"""
import pandas as pd

from common import PROCESSED, load_sources, load_states
from load_manual import load_ndhs_manual

CROSSCHECK_THRESHOLD_PCT = 20

# Per-100,000 rates rest on modelled population, so keep one decimal at most (data trap 4).
RATE_DECIMALS = 1


def facility_counts() -> pd.DataFrame:
    g = pd.read_csv(PROCESSED / "facilities_grid3.csv")
    e = pd.read_csv(PROCESSED / "facilities_ehealthafrica.csv")
    lv = pd.crosstab(g.state, g.level)
    out = pd.DataFrame({
        "fac_all_grid3": g.groupby("state").size(),
        "fac_primary_grid3": lv.get("primary"),
        "fac_secondary_grid3": lv.get("secondary"),
        "fac_tertiary_grid3": lv.get("tertiary"),
        "fac_level_unknown_grid3": lv.get("unknown"),
        "fac_sec_tert_public_grid3": g[g.level.isin(["secondary", "tertiary"]) & (g.ownership == "public")]
        .groupby("state").size(),
        "fac_all_eha": e.groupby("state").size(),
        "fac_sec_tert_eha": e[e.level.isin(["secondary", "tertiary"])].groupby("state").size(),
    }).fillna(0).astype(int)
    out["fac_sec_tert_grid3"] = out.fac_secondary_grid3 + out.fac_tertiary_grid3
    return out


def dhs_wide() -> pd.DataFrame:
    d = pd.read_csv(PROCESSED / "dhs_state_long.csv")
    w = d.pivot(index="state", columns="IndicatorId", values="Value")
    out = pd.DataFrame({
        "insurance_any_men_pct": w["AH_HINS_M_ANY"],
        "insurance_none_women_pct": w["AH_HINS_W_NON"],
        "insurance_any_women_pct": (100 - w["AH_HINS_W_NON"]).round(1),
        "wealth_q4_pct": w["HC_WIXQ_P_4TH"],
        "wealth_q5_pct": w["HC_WIXQ_P_HGH"],
        "wealth_top2_pct": (w["HC_WIXQ_P_4TH"] + w["HC_WIXQ_P_HGH"]).round(1),
        "barrier_distance_women_pct": w["RH_PAHC_W_DIS"],
        "barrier_money_women_pct": w["RH_PAHC_W_MON"],
    })
    return out


def ndhs_manual_wide() -> pd.DataFrame:
    m = load_ndhs_manual()
    m["col"] = (m.indicator.str.replace("blood_pressure", "bp").str.replace("blood_sugar", "sugar")
                .str.replace("_pct", "") + "_" + m.sex + "_pct")
    return m.pivot(index="state", columns="col", values="value")


def build_panel() -> pd.DataFrame:
    states = load_states()[["state", "state_code", "zone"]].set_index("state")
    pop = pd.read_csv(PROCESSED / "population_state.csv").set_index("state")[["population_total", "population_40plus"]]
    pop["population_total"] = pop["population_total"].round(-3).astype(int)  # modelled: nearest thousand
    panel = states.join(pop).join(facility_counts()).join(dhs_wide()).join(ndhs_manual_wide())
    per = 100_000 / panel.population_total
    panel["fac_all_per_100k"] = (panel.fac_all_grid3 * per).round(RATE_DECIMALS)
    panel["fac_sec_tert_per_100k"] = (panel.fac_sec_tert_grid3 * per).round(RATE_DECIMALS)
    panel["crosscheck_diff_percent"] = ((panel.fac_all_grid3 - panel.fac_all_eha) / panel.fac_all_eha * 100).round(0)
    panel["crosscheck_flag"] = panel.crosscheck_diff_percent.abs() > CROSSCHECK_THRESHOLD_PCT
    panel["crosscheck_sec_tert_diff_percent"] = (
        (panel.fac_sec_tert_grid3 - panel.fac_sec_tert_eha) / panel.fac_sec_tert_eha * 100).round(0)
    panel["crosscheck_sec_tert_flag"] = panel.crosscheck_sec_tert_diff_percent.abs() > CROSSCHECK_THRESHOLD_PCT
    return panel.reset_index()


def build_dictionary(panel: pd.DataFrame) -> pd.DataFrame:
    src = load_sources()
    dhs_pull = pd.read_csv(PROCESSED / "dhs_state_long.csv")["pulled"].iloc[0]
    rows = {
        "state": ("Official state name", "", "lookup", "", ""),
        "state_code": ("ISO 3166-2 code", "", "lookup", "", ""),
        "zone": ("Geopolitical zone", "", "lookup", "", ""),
        "population_total": ("Modelled population, 2025 estimate, rounded to nearest 1,000", "people", "grid3_pop_v3", "", ""),
        "population_40plus": ("Population aged 40+", "people", "grid3_pop_v3", "", "unknown: no age-sex groups in source file"),
        "fac_all_grid3": ("Health facilities, all levels, after de-duplication", "count", "grid3_hf_v2", "", ""),
        "fac_primary_grid3": ("Primary-level facilities", "count", "grid3_hf_v2", "", "level via facility_levels.csv"),
        "fac_secondary_grid3": ("Secondary-level facilities", "count", "grid3_hf_v2", "", "level via facility_levels.csv"),
        "fac_tertiary_grid3": ("Tertiary-level facilities", "count", "grid3_hf_v2", "", "level via facility_levels.csv"),
        "fac_level_unknown_grid3": ("Facilities with no level recorded", "count", "grid3_hf_v2", "", ""),
        "fac_sec_tert_grid3": ("Secondary + tertiary facilities", "count", "grid3_hf_v2", "", "secondary + tertiary"),
        "fac_sec_tert_public_grid3": ("Public secondary + tertiary facilities", "count", "grid3_hf_v2", "", "ownership = public"),
        "fac_all_eha": ("Health facilities, all levels (cross-check)", "count", "ehealthafrica_hf", "", "not de-duplicated"),
        "fac_sec_tert_eha": ("Secondary + tertiary facilities (cross-check)", "count", "ehealthafrica_hf", "", ""),
        "fac_all_per_100k": ("Facilities per 100,000 people", "per 100,000", "grid3_hf_v2; grid3_pop_v3", "", "fac_all_grid3 / population_total x 100,000; 1 decimal"),
        "fac_sec_tert_per_100k": ("Secondary + tertiary facilities per 100,000 people", "per 100,000", "grid3_hf_v2; grid3_pop_v3", "", "fac_sec_tert_grid3 / population_total x 100,000; 1 decimal"),
        "crosscheck_diff_percent": ("GRID3 count vs eHealth Africa count", "% difference", "grid3_hf_v2; ehealthafrica_hf", "", "(GRID3 - eHA) / eHA x 100"),
        "crosscheck_flag": ("Counts differ by more than 20%", "true/false", "grid3_hf_v2; ehealthafrica_hf", "", "abs(crosscheck_diff_percent) > 20"),
        "crosscheck_sec_tert_diff_percent": ("GRID3 vs eHealth Africa, secondary + tertiary only", "% difference", "grid3_hf_v2; ehealthafrica_hf", "", "(GRID3 - eHA) / eHA x 100"),
        "crosscheck_sec_tert_flag": ("Secondary + tertiary counts differ by more than 20%", "true/false", "grid3_hf_v2; ehealthafrica_hf", "", "abs(crosscheck_sec_tert_diff_percent) > 20"),
        "insurance_any_men_pct": ("Men 15-49 with any health insurance", "%", "ndhs2024_api", "", "AH_HINS_M_ANY"),
        "insurance_none_women_pct": ("Women 15-49 with no health insurance", "%", "ndhs2024_api", "", "AH_HINS_W_NON"),
        "insurance_any_women_pct": ("Women 15-49 with any health insurance", "%", "ndhs2024_api", "", "calculated: 100 - AH_HINS_W_NON"),
        "wealth_q4_pct": ("Household population in 4th wealth quintile", "%", "ndhs2024_api", "", "HC_WIXQ_P_4TH"),
        "wealth_q5_pct": ("Household population in highest wealth quintile", "%", "ndhs2024_api", "", "HC_WIXQ_P_HGH"),
        "wealth_top2_pct": ("Household population in top two wealth quintiles", "%", "ndhs2024_api", "", "calculated: HC_WIXQ_P_4TH + HC_WIXQ_P_HGH"),
        "barrier_distance_women_pct": ("Women 15-49 for whom distance is a big problem in getting care", "%", "ndhs2024_api", "", "RH_PAHC_W_DIS"),
        "barrier_money_women_pct": ("Women 15-49 for whom getting money is a big problem in getting care", "%", "ndhs2024_api", "", "RH_PAHC_W_MON"),
    }
    for topic, label, t_w, t_m, p_w, p_m in [("bp", "blood pressure", "19.1.1", "19.1.2", 587, 589),
                                            ("sugar", "blood sugar", "19.2.1", "19.2.2", 591, 593)]:
        for sex, t, p in [("women", t_w, p_w), ("men", t_m, p_m)]:
            rows[f"{topic}_ever_measured_{sex}_pct"] = (f"{sex.title()} 15-49 who ever had {label} measured", "%", "ndhs2024_fr395", "", f"Table {t}, p.{p}; self-reported")
            rows[f"{topic}_ever_told_high_{sex}_pct"] = (f"{sex.title()} 15-49 ever told they have high {label}", "%", "ndhs2024_fr395", "", f"Table {t}, p.{p}; self-reported, not measured prevalence")
    out = []
    for col in panel.columns:
        desc, unit, sid, _, how = rows.get(col, ("", "", "", "", ""))
        ids = [s.strip() for s in sid.split(";") if s.strip()]
        dates = []
        for s in ids:
            if s == "lookup":
                dates.append("lookup table (no date)")
            elif s == "ndhs2024_api":
                dates.append(f"{src[s]['data_as_of']}; pulled {dhs_pull}")
            else:
                dates.append(f"{src[s]['data_as_of']}; accessed {src[s]['date_accessed']}")
        out.append({"column": col, "description": desc, "unit": unit, "source_id": sid,
                    "data_date": " | ".join(dates), "derivation": how})
    return pd.DataFrame(out)


def main() -> pd.DataFrame:
    panel = build_panel()
    panel.to_csv(PROCESSED / "state_panel.csv", index=False)
    build_dictionary(panel).to_csv(PROCESSED / "state_panel_dictionary.csv", index=False)
    print(f"  state_panel.csv: {len(panel)} rows x {panel.shape[1]} columns")
    return panel


if __name__ == "__main__":
    main()
