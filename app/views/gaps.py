"""Page 4: Specialist gaps. What the hand-built register says about capacity, and what is missing.
Kidney (dialysis) and cancer (radiotherapy) use the same register rules and the same layout."""
import html

import plotly.graph_objects as go
import streamlit as st

import chart_style as cs
import charts
import components as ui
import story

ui.setup()
names = ui.display_names()
choice = st.segmented_control("Specialty", ["Kidney care", "Cancer care"], default="Kidney care",
                              key="gap_spec", label_visibility="collapsed") or "Kidney care"
cancer = choice == "Cancer care"
spec = "cancer" if cancer else "kidney"
rows = ui.csv(f"register_{spec}_rows.csv", dtype=str, keep_default_na=False)
nat = ui.csv(f"register_{spec}_national.csv", dtype=str, keep_default_na=False)
by_state = ui.csv(f"register_{spec}_by_state.csv")
panel = ui.csv("state_panel.csv")

if cancer:
    ui.opening("Where is radiotherapy missing, and why?",
               "Radiotherapy treats cancer with radiation from a **linac** (linear accelerator) or a cobalt-60 unit. "
               "There is no clean public list of these machines, so I built one by hand: one row per fact, from one "
               "source, with its date. When sources disagree, both rows stay.")
else:
    ui.opening("Where is dialysis missing, and why?",
               "There is no clean public list of dialysis capacity in Nigeria, so I built one by hand: one row per "
               "fact, from one source, with its date. When sources disagree, both rows stay.")

# ---------- the sources don't agree ----------
st.subheader("The sources don't agree")
if cancer:
    groups = charts.cancer_national_groups(nat)
    work = groups["Working radiotherapy machines (any type)"].sort_values(["n", "source_date"])
    need = groups["Machines needed"].sort_values("source_date")
    picks = [("Working machines: lowest count", work.iloc[0]),
             ("Working machines: highest count", work.iloc[-1]),
             ("Machines needed (latest estimate)", need.iloc[-1])]
else:
    n = nat[nat["count"].str.strip() != ""].assign(v=lambda d: d["count"].astype(float))
    n["who"] = n.source_url.str.extract(r"https?://([^/]+)/")[0].map(charts.SOURCE_LABELS).fillna("other source")
    centres = n[(n.item == "dialysis centre") & (n.ownership == "mixed")].sort_values(["v", "source_date"])
    machines = n[(n.item == "dialysis machine") & (n.status == "working")].sort_values(["v", "source_date"])
    picks = [("Dialysis centres: lowest count", centres.iloc[0]),
             ("Dialysis centres: highest count", centres.iloc[-1]),
             ("Working dialysis machines", machines.iloc[-1])]
cols = st.columns(3)
for i, (c, (label, r)) in enumerate(zip(cols, picks)):
    v = float(r["count"])
    who = r["who"] if "who" in r else charts.cancer_source_label(r.source_url)
    with c:
        with st.container(key=f"panel_conflict_{i}"):
            st.html(f'<div class="small-grey">{html.escape(label)}</div>'
                    f'<div class="big-number" style="font-size:1.9rem">{v:,.0f}'
                    f'{" working" if r.status == "working" else ""}</div>'
                    f'<div class="small-grey">{html.escape(who)} · {r.source_date} · '
                    f'<a href="{r.source_url}" target="_blank">source</a></div>')
nn = nat[nat["count"].str.strip() != ""]
st.caption(f"{len(nn)} national figures in the register, from {nn.source_date.min()[:4]} to "
           f"{nn.source_date.max()[:4]}. Some count every machine, some only working ones; some are upper bounds "
           "('fewer than 20'). None is averaged.")
if cancer:
    with st.expander("All the national radiotherapy figures, side by side"):
        ui.chart(charts.national_counts_cancer(nat), key="gap_cancer_nat")

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
        ui.chart(bar, key=f"gap_bar_{spec}")
        legend = st.columns(2)
        for i, t in enumerate(cs.GAP_COLOURS):
            legend[i % 2].html(f'<div style="font-size:.92rem"><span style="color:{cs.GAP_COLOURS[t]}">■</span> '
                               f'{t.title()} <b>{g[t]}</b> rows</div>')
        known = g.drop("unknown")
        top = known[known == known.max()].index.tolist()
        st.html(f'<div class="small-grey" style="margin-top:8px">Of {int(g.sum())} state-level facts, '
                f'{int(known.sum())} say what the gap is; <b>{" and ".join(top)}</b> problems come up most'
                f'{" (power, water, consumables, maintenance, payment)" if top == ["systems"] else ""}. '
                f'"Unknown" means the source doesn\'t say, not that nothing is missing.</div>')
        found = int((by_state.evidence == "found").sum())
        st.html(f'<div class="small-grey" style="margin-top:6px">{found} of 37 states have any evidence in the '
                f'register. {story.public_unit_sentence(by_state, "radiotherapy" if cancer else "dialysis")}</div>')
with right:
    with st.container(border=True):
        st.markdown("**Capacity per million people, by state**")
        ui.chart(charts.machines_per_million_bars(by_state, panel, "Cancer" if cancer else "Kidney",
                                                  "Working radiotherapy machines" if cancer else "Working machines"),
                 key=f"gap_per_million_{spec}")

# ---------- the register ----------
st.subheader("The register")
f1, f2 = st.columns([2, 1])
status = f1.pills("Status", ["working", "not working", "unknown"], selection_mode="multi",
                  default=["working", "not working", "unknown"], key=f"gap_status_{spec}")
where = f2.selectbox("State", ["All", "National", *sorted(panel.state, key=names.get)], key=f"gap_state_{spec}",
                     format_func=lambda s: names.get(s, s))
t = rows[rows.status.isin(status or ["working", "not working", "unknown"])]
if where != "All":
    t = t[t.state == where]
st.dataframe(t, hide_index=True, width="stretch", height=420,
             column_config={"source_url": st.column_config.LinkColumn("source_url"),
                            "evidence_note": st.column_config.TextColumn("evidence_note", width="large")})
st.caption(f"{len(t)} of {len(rows)} rows. Columns as in the brief (section 4.6). News sources are labelled "
           "'news'; prefer peer-reviewed and government rows where they exist.")
ui.download(t, f"{spec}_register.csv")

ui.footer(f"{spec.title()} register (news, government, peer-reviewed sources; one row per fact) · "
          "GRID3/WorldPop v3.0",
          f"register sources {rows.source_date.min()} to {rows.source_date.max()}, accessed "
          f"{rows.date_accessed.max()}")
