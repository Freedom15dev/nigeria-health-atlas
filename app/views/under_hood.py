"""Page 7: Under the hood. Sources, conflicting figures, data traps, scoring method, limits."""
import pandas as pd
import streamlit as st

import charts
import components as ui
import scoring

ui.setup()
m = ui.meta()
panel = ui.csv("state_panel.csv")
hf = ui.csv("headline_figures.csv", dtype=str, keep_default_na=False)
wdi = ui.csv("wdi_nga.csv")
reg = ui.csv("register_kidney_rows.csv", dtype=str, keep_default_na=False)
steps = m["pipeline_steps"]

ui.opening("How was this built, and where is it weak?",
           "Every number in this app comes from a public source with a date, through code. Where sources "
           "disagree, all the figures are kept. Where data is missing, it says unknown.")

st.header("Sources")
src = ui.csv("sources.csv", dtype=str, keep_default_na=False)
st.dataframe(src[["name", "publisher", "date_accessed", "data_as_of", "licence", "url", "notes"]], hide_index=True,
             width="stretch", column_config={"url": st.column_config.LinkColumn("url"),
                                             "notes": st.column_config.TextColumn("notes", width="large")})
ui.download(src, "sources.csv")

st.header("Figures that disagree")
st.subheader("How much health spending is paid out of pocket?")
st.markdown("**Out-of-pocket** = paid by the patient or family at the point of care, not through insurance or "
            "government. It is a national figure; this app never spreads it across states.")
ui.chart(charts.oop_figures(hf, wdi), key="uh_oop")
t = charts.oop_table(hf, wdi)
st.dataframe(t[["who", "figure", "date", "measures", "url"]], hide_index=True, width="stretch",
             column_config={"url": st.column_config.LinkColumn("url")})
st.markdown("Likely reasons they differ: **different years** (2023, 2024, or not stated); **different "
            "denominators** (total health expenditure includes capital spending, current health expenditure "
            "doesn't); **different methods** (the National Health Accounts vs World Bank modelled series); and two "
            "of the figures are second-hand news reports of documents I haven't seen.")
st.subheader("The headline figures, row by row")
st.dataframe(hf, hide_index=True, width="stretch", column_config={"url": st.column_config.LinkColumn("url")})
ui.download(hf, "headline_figures.csv")
st.subheader("National dialysis counts")
nat = ui.csv("register_kidney_national.csv", dtype=str, keep_default_na=False)
ui.chart(charts.national_counts(nat), key="uh_nat")

st.subheader("National radiotherapy counts")
cnat = ui.csv("register_cancer_national.csv", dtype=str, keep_default_na=False)
ui.chart(charts.national_counts_cancer(cnat), key="uh_cancer_nat")
st.markdown("Why they differ: some count every machine, some only working ones; some count linacs only; some "
            "are upper bounds ('fewer than 20'); and machines break down and are repaired, so a count is true only "
            "on its date. This spread is why an on-the-ground assessment has to come first.")

st.header("Data traps")
dup = steps["grid3"]["duplicates_dropped"]
flags = int(panel.crosscheck_flag.sum())
flags_st = int(panel.crosscheck_sec_tert_flag.sum())
pc = ui.csv("population_crosscheck.csv")
pcf = pc[pc.flag].sort_values("share_diff_pct", key=abs, ascending=False)
og, la = pc.set_index("state").loc["Ogun"], pc.set_index("state").loc["Lagos"]
popnote = (f"GRID3/WorldPop (2025) puts Ogun at {og.population_grid3_2025 / 1e6:.1f}m people, above Lagos "
           f"({la.population_grid3_2025 / 1e6:.1f}m). The National Population Commission's {int(pc.npc_year.iloc[0])} "
           f"projection (NBS Demographic Bulletin 2023) has Ogun at {og.population_npc / 1e6:.1f}m and Lagos at "
           f"{la.population_npc / 1e6:.1f}m. Comparing each state's share of the national total (the years differ), "
           f"{len(pcf)} states differ by more than 20%: "
           + ", ".join(f"{r.state} ({r.share_diff_pct:+.0f}%)" for r in pcf.itertuples())
           + ". I use GRID3 because it is one consistent model for all 37 states, built from satellite and survey "
           "data rather than projected forward from the 2006 census. Because need is measured by population, this "
           "choice moves states on the scorecard; the full comparison is in exports/.")
traps = [
    ("State names", "Spellings vary between sources (FCT, Federal Capital Territory, Abuja; Nassarawa; Akwa-Ibom; "
     "'..FCT Abuja' in the DHS API). One lookup table, data/lookups/states.csv, holds the name each source uses; "
     "the pipeline stops if any name doesn't match."),
    ("Facility levels", "Sources label levels differently. Each source's labels are mapped to primary / secondary / "
     "tertiary in data/lookups/facility_levels.csv."),
    ("Non-validated registry", f"GRID3 calls its facility data non-exhaustive and non-validated. {dup} duplicate "
     f"rows (same name and LGA, under 100 m apart) were dropped. Against eHealth Africa, {flags} of 37 states "
     f"differ by more than 20% on all facilities, and {flags_st} on secondary + tertiary (the two label levels "
     "differently). Most GRID3 coordinates come from eHealth Africa, so the two lists aren't independent."),
    ("Modelled population", "Nigeria has had no census since 2006. Population figures are GRID3/WorldPop modelled "
     "estimates for 2025, so per-100,000 rates are shown to one decimal place at most. Population aged 40+ is "
     "unknown in this release, so need uses total population."),
    ("Two population estimates disagree", popnote),
    ("Survey margins of error", "NDHS 2024 state figures come from samples; small differences between states can "
     "be noise. The DHS API gives no state-level confidence intervals. Blood pressure and blood sugar are "
     "self-reported diagnoses for ages 15–49, so they partly measure access to testing."),
    ("Conflicting counts", "Out-of-pocket share, dialysis centres and radiotherapy machines all have several "
     "published figures. All are kept with their dates; none is averaged."),
    ("Functional vs installed", "A machine that exists isn't a machine that works. The register's status column "
     f"says working, not working or unknown; {int((reg.status == 'unknown').sum())} of {len(reg)} kidney rows "
     "are unknown."),
    ("National vs state", "The out-of-pocket share is national only. It is never shown as a state figure."),
]
for title, body in traps:
    with st.expander(title):
        st.markdown(body)

st.header("How the scorecard works")
st.markdown(f"**{ui.SCREENING}**")
st.markdown(scoring.__doc__.split("How a score is built, in plain words:")[1].strip())
rows = [{"pillar": scoring.PILLAR_NAMES[p], "input": c, "direction": "higher = more" if d > 0 else "lower = more"}
        for p, ins in scoring.PILLARS.items() for c, d in ins]
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
sens = ui.csv("scorecard_sensitivity_need.csv")
sc_main = ui.csv("scorecard.csv")
sc_dx = scoring.build_scorecard(panel, pillars=scoring.PILLARS_NEED_WITH_DIAGNOSES)
corr = lambda d, a, b: d[[a, b]].corr(method="spearman").iloc[0, 1]
st.markdown("**Check: need with self-reported diagnoses.** The main score measures need by population only. "
            "NDHS 2024 also asks whether a health worker ever *told* people (aged 15-49) they have high blood "
            "pressure or high blood sugar. That partly measures who gets tested, which rises with wealth, so it is "
            "kept as a check, not in the ranking:")
st.dataframe(pd.DataFrame({
    "Need measured by": ["Population only (main score)", "Population + self-reported diagnoses (check)"],
    "Need vs ability to pay (rank corr.)": [f"{corr(sc_main, 'score_need', 'score_ability_to_pay'):+.2f}",
                                            f"{corr(sc_dx, 'score_need', 'score_ability_to_pay'):+.2f}"],
    "Supply gap vs ability to pay": [f"{corr(sc_main, 'score_supply_gap', 'score_ability_to_pay'):+.2f}",
                                     f"{corr(sc_dx, 'score_supply_gap', 'score_ability_to_pay'):+.2f}"],
    "States in the high-need, low-pay corner": [
        int(((sc_main.score_need >= 50) & (sc_main.score_ability_to_pay < 50)).sum()),
        int(((sc_dx.score_need >= 50) & (sc_dx.score_ability_to_pay < 50)).sum())],
}), hide_index=True, width="stretch")
st.dataframe(sens, hide_index=True, width="stretch")

ps = ui.csv("scorecard_sensitivity_population.csv")
yr = int(ps.npc_year.iloc[0])
both = ps[(ps["rank"] <= 10) & (ps.rank_npc_population <= 10)].sort_values("rank")
og = ps.set_index("state").loc["Ogun"]
st.markdown(f"**Check: a different population source.** Need is measured by population, and hospitals per 100,000 "
            f"people divide by it, so the population estimate matters. Re-running the scorecard with the National "
            f"Population Commission's {yr} projection instead of GRID3/WorldPop: {len(both)} of the top 10 stay in "
            f"the top 10 under both ({', '.join(both.state)}). Ogun moves from rank {int(og['rank'])} to "
            f"{int(og.rank_npc_population)}: its place depends on the source.")
st.dataframe(ps.sort_values("rank")[["state", "rank", "rank_npc_population", "rank_change", "score_total",
                                     "score_total_npc_population"]].rename(columns={
    "rank": "rank (GRID3)", "rank_npc_population": f"rank (NPC {yr})", "rank_change": "places moved (+ = down)",
    "score_total": "score (GRID3)", "score_total_npc_population": f"score (NPC {yr})"}),
    hide_index=True, width="stretch")
ui.download(ps, "scorecard_sensitivity_population.csv")
st.markdown("The stress test re-runs the score with each weight between 20% and 50% (steps of 5%, rescaled to "
            "add up to 100%) and counts how often each state stays in the top 10.")

st.header("Limits")
gap_unknown = int((reg.gap_type == "unknown").sum())
creg = ui.csv("register_cancer_rows.csv", dtype=str, keep_default_na=False)
cby = ui.csv("register_cancer_by_state.csv")
st.markdown(f"""
- The kidney register is hand-built from {reg.source_url.nunique()} source pages; most are news reports. Of
  {len(reg)} rows, {gap_unknown} don't say whether the gap is equipment, workforce or systems.
- The centre model is illustrative: many of its inputs are assumptions, flagged as such in
  config/assumptions_kidney.yaml. PPP structures in it are general examples, not any real firm's terms.
- Three headline figures rest on news reports of documents not yet found (the National Health Accounts 2023–24,
  a World Bank programme document, the IARC 2025 assessment).
- The cancer register has {len(creg)} rows from {creg.source_url.nunique()} source pages, with evidence for
  {int((cby.evidence == "found").sum())} of 37 states. States with no rows are "no evidence found", not "no
  radiotherapy".
- Map boundaries: geoBoundaries (from GRID3 state boundaries), CC BY 4.0, simplified for display.

**This is a learning project using public data. It is not investment, medical or financial advice.**
""")

ui.footer("all sources listed above", f"pipeline built {m['built']}")
