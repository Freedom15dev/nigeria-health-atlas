"""Page 4: Specialist gaps. What the hand-built register says about capacity, and what is missing."""
import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import chart_style as cs
import charts
import components as ui
import story

ui.setup()
names = ui.display_names()
spec = st.segmented_control("Specialty", ["Kidney care", "Cancer care"], default="Kidney care",
                            key="gap_spec", label_visibility="collapsed") or "Kidney care"

if spec == "Cancer care":
    ui.opening("Where is radiotherapy missing, and why?",
               "The cancer register (radiotherapy machines, oncologists) is built in phase 6, with the same "
               "rules as the kidney register. Until then, here are the national figures.")
    hf = ui.csv("headline_figures.csv", dtype=str, keep_default_na=False)
    rt = hf[hf.card == "2"]
    cols = st.columns(len(rt))
    for c, r in zip(cols, rt.itertuples()):
        c.html(ui.card(r.label, f"{'over ' if r.qualifier == 'over' else 'about ' if r.qualifier == 'about' else ''}"
                       f"{float(r.figure):,.0f}", "",
                       f"{html.escape(r.source_short)} · {r.source_date}", kind=""))
    st.info("Until the cancer register exists, capacity by state, gap types and the register table are [—].")
    ui.footer("headline figures (see Under the hood)", "")
    st.stop()

ui.opening("Where is dialysis missing, and why?",
           "There is no clean public list of dialysis capacity in Nigeria, so I built one by hand: one row per "
           "fact, from one source, with its date. When sources disagree, both rows stay.")
rows = ui.csv("register_kidney_rows.csv", dtype=str, keep_default_na=False)
nat = ui.csv("register_kidney_national.csv", dtype=str, keep_default_na=False)
by_state = ui.csv("register_kidney_by_state.csv")
panel = ui.csv("state_panel.csv")

# ---------- the sources don't agree ----------
st.subheader("The sources don't agree")
n = nat[nat["count"].str.strip() != ""].assign(v=lambda d: d["count"].astype(float))
n["who"] = n.source_url.str.extract(r"https?://([^/]+)/")[0].map(charts.SOURCE_LABELS).fillna("other source")
centres = n[(n.item == "dialysis centre") & (n.ownership == "mixed")].sort_values(["v", "source_date"])
machines = n[(n.item == "dialysis machine") & (n.status == "working")].sort_values(["v", "source_date"])
picks = [("Dialysis centres: lowest count", centres.iloc[0]),
         ("Dialysis centres: highest count", centres.iloc[-1]),
         ("Working dialysis machines", machines.iloc[-1])]
cols = st.columns(3)
for i, (c, (label, r)) in enumerate(zip(cols, picks)):
    with c:
        with st.container(key=f"panel_conflict_{i}"):
            st.html(f'<div class="small-grey">{html.escape(label)}</div>'
                    f'<div class="big-number" style="font-size:1.9rem">{r.v:,.0f}'
                    f'{" working" if r.status == "working" else ""}</div>'
                    f'<div class="small-grey">{html.escape(r.who)} · {r.source_date} · '
                    f'<a href="{r.source_url}" target="_blank">source</a></div>')
st.caption(f"{len(n)} national figures in the register, from {n.source_date.min()[:4]} to "
           f"{n.source_date.max()[:4]}. Some count every centre, some only working ones; none is averaged.")

# ---------- gap type + capacity per million ----------
left, right = st.columns([1, 1.25], gap="large")
with left:
    with st.container(border=True):
        st.markdown("**What is missing: the gap type**")
        state_rows = rows[rows.state != "National"]
        g = state_rows.gap_type.value_counts().reindex(list(cs.GAP_COLOURS), fill_value=0)
        bar = go.Figure()
        for t, colour in cs.GAP_COLOURS.items():
            bar.add_trace(go.Bar(x=[g[t]], y=[""], orientation="h", marker_color=colour, name=t.title(),
                                 hovertemplate=f"{t.title()}: %{{x}} rows<extra></extra>"))
        bar.update_layout(barmode="stack", height=70, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                          paper_bgcolor="white", plot_bgcolor="white", xaxis=dict(visible=False),
                          yaxis=dict(visible=False))
        ui.chart(bar, key="gap_bar")
        legend = st.columns(2)
        for i, t in enumerate(cs.GAP_COLOURS):
            legend[i % 2].html(f'<div style="font-size:.92rem"><span style="color:{cs.GAP_COLOURS[t]}">■</span> '
                               f'{t.title()} <b>{g[t]}</b> rows</div>')
        known = g.drop("unknown")
        st.html(f'<div class="small-grey" style="margin-top:8px">Of {int(g.sum())} state-level facts, '
                f'{int(known.sum())} say what the gap is; <b>{known.idxmax()}</b> problems come up most'
                f'{" (power, water, consumables, maintenance, payment)" if known.idxmax() == "systems" else ""}. "Unknown" means the source doesn\'t say, not '
                f'that nothing is missing.</div>')
        st.html(f'<div class="small-grey" style="margin-top:6px">{story.public_dialysis_sentence(by_state)}</div>')
with right:
    with st.container(border=True):
        st.markdown("**Capacity per million people, by state**")
        ui.chart(charts.machines_per_million_bars(by_state, panel), key="gap_per_million")

# ---------- the register ----------
st.subheader("The register")
f1, f2 = st.columns([2, 1])
status = f1.pills("Status", ["working", "not working", "unknown"], selection_mode="multi",
                  default=["working", "not working", "unknown"], key="gap_status")
where = f2.selectbox("State", ["All", "National", *sorted(panel.state, key=names.get)], key="gap_state",
                     format_func=lambda s: names.get(s, s))
t = rows[rows.status.isin(status or ["working", "not working", "unknown"])]
if where != "All":
    t = t[t.state == where]
st.dataframe(t, hide_index=True, width="stretch", height=420,
             column_config={"source_url": st.column_config.LinkColumn("source_url"),
                            "evidence_note": st.column_config.TextColumn("evidence_note", width="large")})
st.caption(f"{len(t)} of {len(rows)} rows. Columns as in the brief (section 4.6). News sources are labelled "
           "'news'; prefer peer-reviewed and government rows where they exist.")
ui.download(t, "kidney_register.csv")

ui.footer("Kidney register (news, government, peer-reviewed sources; one row per fact) · GRID3/WorldPop v3.0",
          f"register sources {rows.source_date.min()} to {rows.source_date.max()}, accessed "
          f"{rows.date_accessed.max()}")
