"""Every number the README and the post drafts quote, computed from data/processed/ and config/.

story_numbers() returns a dict of ready-to-print strings. The templates in story/ only contain
{placeholders}; pipeline/build_story.py fills them. Nothing here types in a figure: if a source file
changes, the text changes with it.
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import yaml

import centre_model as M
import charts
import story
from story import naira, short_state

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"


def _pct(v: float, digits: int = 0) -> str:
    return f"{v:.{digits}f}%"


def _n(v: float) -> str:
    return f"{v:,.0f}"


def _list(items: list[str]) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _money(v: float) -> str:
    """₦4.7m style for big sums, ₦45,000 style for small ones."""
    return naira(v, short=abs(v) >= 1e6)


def story_numbers() -> dict[str, str]:
    s: dict[str, str] = {}
    meta = yaml.safe_load((ROOT / "config" / "story.yaml").read_text(encoding="utf-8"))["halima"]
    panel = pd.read_csv(P / "state_panel.csv")
    sc = pd.read_csv(P / "scorecard.csv")
    stress = pd.read_csv(P / "scorecard_stress.csv")
    sens_need = pd.read_csv(P / "scorecard_sensitivity_need.csv")
    reg_k = pd.read_csv(P / "register_kidney_rows.csv", dtype=str, keep_default_na=False)
    reg_c = pd.read_csv(P / "register_cancer_rows.csv", dtype=str, keep_default_na=False)
    by_k = pd.read_csv(P / "register_kidney_by_state.csv")
    by_c = pd.read_csv(P / "register_cancer_by_state.csv")
    nat_k = pd.read_csv(P / "register_kidney_national.csv", dtype=str, keep_default_na=False)
    nat_c = pd.read_csv(P / "register_cancer_national.csv", dtype=str, keep_default_na=False)
    dist = pd.read_csv(P / "state_dialysis_distance.csv")
    lga = pd.read_csv(P / "lga_dialysis_distance.csv")
    hf = pd.read_csv(P / "headline_figures.csv", dtype=str, keep_default_na=False)
    wdi = pd.read_csv(P / "wdi_nga.csv")
    meta_json = pd.read_json(P / "meta.json", typ="series")
    a = M.load_assumptions()
    ac = M.load_assumptions(M.ASSUMPTIONS_CANCER)

    # ---------- Halima ----------
    st = meta["state"]
    s["halima_age"], s["halima_job"], s["halima_state"] = str(meta["age"]), meta["occupation"], short_state(st)
    lo_s = a["capacity"]["sessions_per_patient_per_week"]["low"]
    hi_s = a["capacity"]["sessions_per_patient_per_week"]["high"]
    p_oop = a["prices"]["price_out_of_pocket_ngn"]["value"]
    p_sub = a["prices"]["price_subsidised_ngn"]["value"]
    s |= {"sessions_lo": str(lo_s), "sessions_hi": str(hi_s), "price_oop": naira(p_oop), "price_sub": naira(p_sub),
          "year_cost_lo": _money(p_oop * lo_s * 52), "year_cost_hi": _money(p_oop * hi_s * 52),
          "year_sub_lo": _money(p_sub * lo_s * 52), "year_sub_hi": _money(p_sub * hi_s * 52),
          "private_price_range": story.headline_cards(hf)[3]["big"]}
    hrow = sc.set_index("state").loc[st]
    prow = panel.set_index("state").loc[st]
    s |= {"h_need": _n(hrow.score_need), "h_gap": _n(hrow.score_supply_gap), "h_pay": _n(hrow.score_ability_to_pay),
          "h_rank": str(int(hrow["rank"])), "h_insured": _pct((prow.insurance_any_women_pct + prow.insurance_any_men_pct) / 2, 1),
          "h_fac": f"{prow.fac_sec_tert_per_100k:.1f}"}
    d = dist.set_index("state").loc[st]
    s |= {"h_median_km": _n(d.median_km_population_weighted), "h_max_km": _n(d.max_km),
          "h_beyond50": _pct(d.share_beyond_50km_pct), "h_beyond100": _pct(d.share_beyond_100km_pct)}
    hl = lga[lga.state == st]
    s["h_nearest_units"] = _list(sorted(hl.nearest_unit.dropna().unique()))
    units = pd.read_csv(ROOT / "data" / "lookups" / "dialysis_unit_locations.csv")
    s["n_units_located"], s["n_unit_states"] = str(len(units)), str(units.state.nunique())
    meas = lga.dropna(subset=["km_straight_line"])
    s["nat_beyond100"] = _pct(100 * meas.loc[meas.km_straight_line > 100, "population"].sum() / meas.population.sum())
    worst = dist[dist.share_beyond_100km_pct >= 80].sort_values("share_beyond_100km_pct", ascending=False)
    s["n_states_80"] = str(len(worst))
    s["states_80"] = _list([short_state(x) for x in worst.state])

    # income comparison (only if a sourced benchmark exists)
    inc_file = MANUAL / "income_benchmarks.csv"
    s["income_sentence"] = ("Her family's income isn't in this data, so what share of it dialysis takes is unknown.")
    s["poverty_sentence"] = ""
    if inc_file.exists():
        inc = pd.read_csv(inc_file)
        mw = inc[inc.measure == "national_minimum_wage"].sort_values("source_date", ascending=False)

        def pick(measure, geo):
            r = inc[(inc.measure == measure) & (inc.geography == geo)].sort_values("source_date")
            return r.iloc[-1] if len(r) else None
        pov_h, pov_n = pick("monetary_poverty_headcount", st), pick("monetary_poverty_headcount", "Nigeria")
        mpi_h, mpi_n = pick("multidimensional_poverty_headcount", st), pick("multidimensional_poverty_headcount", "Nigeria")
        line = pick("national_poverty_line", "Nigeria")
        if pov_h is not None and mpi_h is not None and pov_n is not None and mpi_n is not None and line is not None:
            s["poverty_sentence"] = (
                f"And money is tight where Halima lives: in {short_state(st)}, {_pct(pov_h.value, 1)} of people lived "
                f"below the national poverty line ({naira(line.value)} per person per year) in {pov_h.reference_year}, "
                f"against {_pct(pov_n.value, 1)} nationally; and {_pct(mpi_h.value, 1)} were multidimensionally poor "
                f"(poor in health, education and living standards, not just income) in {mpi_h.reference_year}, against "
                f"{_pct(mpi_n.value, 1)} nationally (NBS).")
        if len(mw):
            w = mw.iloc[0]
            yearly_wage = float(w.value) * 12
            s["min_wage"] = naira(float(w.value))
            when = pd.Timestamp(str(w.source_date)[:7] + "-01")
            s["min_wage_source"] = (f"set in {int(w.reference_year)}, still the rate in {when:%B %Y} "
                                    f"according to {w.source.split(' (')[0]}")
            s["cost_vs_wage_lo"] = f"{p_oop * lo_s * 52 / yearly_wage:.1f}"
            s["cost_vs_wage_sub"] = f"{p_sub * lo_s * 52 / yearly_wage:.1f}"
            s["income_sentence"] = (
                f"For scale: the national minimum wage is {s['min_wage']} a month ({s['min_wage_source']}). "
                f"Twice-weekly dialysis at {s['price_oop']} a session costs {s['cost_vs_wage_lo']} times a full year of "
                f"minimum-wage pay; at the subsidised price, {s['cost_vs_wage_sub']} times. Halima is a trader, not a "
                "wage earner, and her family's actual income is unknown, so this is a yardstick, not her budget.")

    # ---------- the gap ----------
    d1 = panel.sort_values("fac_sec_tert_per_100k")
    low, high = d1.iloc[0], d1.iloc[-1]
    s |= {"fac_low_state": short_state(low.state), "fac_low": f"{low.fac_sec_tert_per_100k:.1f}",
          "fac_high_state": short_state(high.state), "fac_high": f"{high.fac_sec_tert_per_100k:.1f}",
          "fac_ratio": f"{high.fac_sec_tert_per_100k / low.fac_sec_tert_per_100k:.0f}",
          "fac_national": f"{panel.fac_sec_tert_grid3.sum() / panel.population_total.sum() * 1e5:.1f}",
          "fac_lowest5": _list([short_state(x) for x in d1.state.head(5)]),
          "low10_north": (lambda k: "All 10" if k == 10 else f"{k} of the 10")(
              int(d1.head(10).zone.str.startswith("North").sum()))}
    col = by_k.public_unit_working.fillna("unknown")
    s |= {"k_public_yes": str(int((col == "yes").sum())), "k_public_no": str(int((col == "reported not working").sum())),
          "k_public_unknown": str(int((col == "unknown").sum()))}
    steps = meta_json["pipeline_steps"]
    s["grid3_dupes"] = str(steps["grid3"]["duplicates_dropped"])
    s["crosscheck_flags"] = str(int(panel.crosscheck_flag.sum()))

    # ---------- the cause ----------
    def gaps(reg):
        g = reg[reg.state != "National"].gap_type.value_counts()
        known = g.drop("unknown", errors="ignore")
        return g, known
    gk, kk = gaps(reg_k)
    gc, kc = gaps(reg_c)
    s |= {"k_state_facts": str(int(gk.sum())), "k_known": str(int(kk.sum())), "k_top_gap": kk.idxmax(),
          "k_systems": str(int(kk.get("systems", 0))), "k_equipment": str(int(kk.get("equipment", 0))),
          "k_workforce": str(int(kk.get("workforce", 0))),
          "c_state_facts": str(int(gc.sum())), "c_known": str(int(kc.sum())),
          "c_systems": str(int(kc.get("systems", 0))), "c_equipment": str(int(kc.get("equipment", 0))),
          "c_workforce": str(int(kc.get("workforce", 0)))}
    q = reg_k[(reg_k.state == st) & reg_k.evidence_note.str.contains("we are few", case=False)]
    s["h_quote"] = q.evidence_note.str.extract(r'"([^"]+)"')[0].iloc[0] if len(q) else ""
    s["h_quote_src"] = f"{charts.cancer_source_label(q.source_url.iloc[0])}, {q.source_date.iloc[0]}" if len(q) else ""

    # ---------- who pays ----------
    oop = charts.oop_table(hf, wdi)
    s |= {"oop_min": _pct(oop.figure.min()), "oop_max": _pct(oop.figure.max()), "oop_n": str(len(oop))}
    d98 = hf[(hf.card == "4") & (hf.role == "context")].iloc[0]
    s["dialysis_oop"] = _pct(float(d98.figure))
    ins = (panel.insurance_any_women_pct + panel.insurance_any_men_pct) / 2
    s["insured_nat"] = _pct((ins * panel.population_total).sum() / panel.population_total.sum(), 1)
    r_need = sc[["score_need", "score_ability_to_pay"]].corr(method="spearman").iloc[0, 1]
    r_gap = sc[["score_supply_gap", "score_ability_to_pay"]].corr(method="spearman").iloc[0, 1]
    s |= {"r_need_pay": f"{r_need:+.2f}".replace("-", "−"), "r_gap_pay": f"{r_gap:+.2f}".replace("-", "−"),
          "orange_corner": str(int(((sc.score_need >= 50) & (sc.score_ability_to_pay < 50)).sum()))}
    robust = stress[stress.share_in_top10_pct >= 80]
    s |= {"top5": _list([short_state(x) for x in sc.head(5).state]),
          "bottom5": _list([short_state(x) for x in sc.tail(5).state]),
          "n_weightings": _n(stress.n_weightings.iloc[0]), "n_robust": str(len(robust)),
          "robust_states": _list([short_state(x) for x in robust.state]),
          "need_pop_only_unchanged": str(int(((sens_need["rank"] <= 10) & (sens_need.rank_need_pop_only <= 10)).sum()))}

    # ---------- one centre ----------
    ks = pd.read_csv(P / "centre_model_scenarios.csv")
    kb = ks[(ks.scenario == "base") & (ks.naira_shock == 0)].iloc[0]
    kh = ks[(ks.scenario == "high") & (ks.naira_shock == 0)].iloc[0]
    kh20 = ks[(ks.scenario == "high") & (ks.naira_shock == 0.2)].iloc[0]
    kinp = list(M.input_specs(a))
    sens_k = pd.read_csv(P / "centre_model_sensitivity.csv")
    s |= {"k_machines": _n(kb.weekly_capacity / (a["capacity"]["shifts_per_day"]["value"]
                                                 * a["capacity"]["days_open_per_week"]["value"])),
          "k_patients": _n(kb.patients_treated), "k_sessions": _n(kb.sessions_per_year),
          "k_used": _pct(kb.capacity_used * 100), "k_price": naira(kb.average_price_ngn),
          "k_breakeven": naira(kb.breakeven_price_ngn), "k_variable": naira(kb.variable_cost_per_session_ngn),
          "k_result": (f"loses about {_money(-kb.net_cash_per_year_ngn)}" if kb.net_cash_per_year_ngn < 0
                       else f"makes about {_money(kb.net_cash_per_year_ngn)}"),
          "k_capex": _money(kb.setup_capital_ngn),
          "k_high_payback": _n(kh.payback_years),
          "k_high20_payback": (f"{_n(kh20.payback_years)} years" if math.isfinite(kh20.payback_years)
                               else "never paying back"),
          "k_fx": _n(kb.fx_ngn_per_usd), "k_fx_year": str(int(kb.fx_year)),
          "k_assumed": str(sum(str(x[2]["source"]).startswith("assumption") for x in kinp)), "k_inputs": str(len(kinp)),
          "k_driver": sens_k.iloc[0].input.replace("_", " ").replace(" usd", " (US$)"),
          "k_driver_sourced": "has a public source" if sens_k.iloc[0].verified else "is an assumption with no public source yet"}
    kp = pd.read_csv(P / "centre_model_ppp.csv")
    kf = kp[(kp.structure == "fee") & (kp.naira_shock == 0)].iloc[0]
    s |= {"ppp_partner": _money(kf.partner_net_cash_ngn), "ppp_hospital": _money(kf.hospital_net_cash_ngn)}
    cs_ = pd.read_csv(P / "centre_model_cancer_scenarios.csv")
    cb = cs_[(cs_.scenario == "base") & (cs_.naira_shock == 0)].iloc[0]
    ch = cs_[(cs_.scenario == "high") & (cs_.naira_shock == 0)].iloc[0]
    cinp = list(M.input_specs(ac))
    sens_c = pd.read_csv(P / "centre_model_cancer_sensitivity.csv")
    s |= {"c_patients": _n(cb.patients_treated), "c_fractions": _n(cb.sessions_per_year),
          "c_price": naira(cb.average_price_per_course_ngn), "c_breakeven": naira(cb.breakeven_price_per_course_ngn),
          "c_net": _money(cb.net_cash_per_year_ngn), "c_be_used": _pct(cb.breakeven_capacity_used * 100),
          "c_high_payback": _n(ch.payback_years), "c_capex": _money(cb.setup_capital_ngn),
          "c_assumed": str(sum(str(x[2]["source"]).startswith("assumption") for x in cinp)), "c_inputs": str(len(cinp)),
          "c_driver": sens_c.iloc[0].input.replace("_", " ").replace("pct of", "% of")}

    # ---------- limits ----------
    nk = nat_k[nat_k["count"].str.strip() != ""].assign(v=lambda x: x["count"].astype(float))
    ck = nk[(nk.item == "dialysis centre") & (nk.ownership == "mixed")]
    s |= {"k_centres_min": _n(ck.v.min()), "k_centres_max": _n(ck.v.max()), "k_spread": f"{ck.v.max() / ck.v.min():.1f}"}
    grp = charts.cancer_national_groups(nat_c)
    w = grp["Working radiotherapy machines (any type)"]
    need = grp["Machines needed"].sort_values("source_date").iloc[-1]
    top = w.sort_values("n").iloc[-1]
    bound = bool(pd.Series(top.evidence_note).str.contains("less than|fewer than|upper bound", case=False).iloc[0])
    s |= {"c_work_min": _n(w.n.min()), "c_work_max": (f"'fewer than {_n(top.n)}'" if bound else _n(top.n)),
          "c_need": _n(need.n),
          "c_need_src": charts.cancer_source_label(need.source_url)}
    lo_m, hi_m, n_m = story.machines_range(by_c)
    s |= {"c_named_machines": _n(hi_m), "c_named_states": str(n_m),
          "c_states_evidence": str(int((by_c.evidence == "found").sum()))}
    s |= {"k_rows": str(len(reg_k)), "c_rows": str(len(reg_c)),
          "k_unknown": str(int((reg_k.gap_type == "unknown").sum())),
          "c_unknown": str(int((reg_c.gap_type == "unknown").sum())),
          "k_news": _pct(100 * (reg_k.source_type == "news").mean()),
          "c_peer": _pct(100 * (reg_c.source_type == "peer-reviewed").mean())}
    log = pd.read_csv(ROOT / "data" / "register" / "verification_log.csv")
    s["n_checked"] = str(len(log))
    s["n_checked_ok"] = str(int(log.verdict.str.startswith("verified").sum()))
    s["built"] = str(meta_json["built"])
    states = pd.read_csv(ROOT / "data" / "lookups" / "states.csv")
    s["n_units"] = str(len(states))
    s["n_states_only"] = str(int((states.state != "Federal Capital Territory").sum()))
    s["band_a"], s["band_b"] = "50", "100"   # distance bands used in state_dialysis_distance.csv
    s["app_url"] = "https://nigeria-health-atlas.streamlit.app/"
    # method thresholds, read from the code that applies them
    import sys
    sys.path.insert(0, str(ROOT / "pipeline"))
    import clean
    import join_states
    s["dedup_m"] = str(clean.DEDUP_METRES)
    s["crosscheck_pct"] = str(join_states.CROSSCHECK_THRESHOLD_PCT)
    s["robust_pct"] = "80"   # threshold used for "robust" in the scorecard stress-test summary
    s["shock_a"] = f"{a['fx']['naira_shocks']['value'][0]:.0%}"
    src = yaml.safe_load((ROOT / "data" / "sources.yaml").read_text(encoding="utf-8"))
    import re
    s["census_year"] = re.search(r"census since (\d{4})", src["grid3_pop_v3"]["notes"]).group(1)
    s["dialysis_oop_year"] = str(d98.source_date)[:4]
    return s
