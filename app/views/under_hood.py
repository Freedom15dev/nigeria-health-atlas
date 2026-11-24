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
st.markdown("**Check: need from population alone.** The self-reported diagnosis figures partly measure access "
            "to testing, so I re-ran the scorecard with need from population only:")
st.dataframe(sens, hide_index=True, width="stretch")
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
