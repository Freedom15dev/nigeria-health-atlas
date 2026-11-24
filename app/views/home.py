"""Page 1: Home. The story on one screen: four headline figures and a map of where to look first."""
import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import chart_style as cs
import components as ui
import story

ui.setup()
names = ui.display_names()
sc = ui.csv("scorecard.csv")
reg = ui.csv("register_kidney_by_state.csv").set_index("state")
halima = story.halima()

if "sel_state" not in st.session_state:
    st.session_state.sel_state = halima["state"]

ui.opening("Where is specialist care missing in Nigeria?")
st.markdown(story.halima_intro(ui.assumptions()) + " " +
            story.distance_sentence(ui.csv("state_dialysis_distance.csv"), halima["state"]))
st.html('<div class="small-grey">Halima is an illustration, not a real person.</div>')

# ---------- four headline cards ----------
cards = story.headline_cards(ui.csv("headline_figures.csv", dtype=str, keep_default_na=False))
cols = st.columns(4)
for col, c in zip(cols, cards):
    src = " · ".join(dict.fromkeys(f"{r['source_short']} ({r['source_date'][:7]})" for r in c["rows"]))
    with col:
        st.html(ui.card(c["label"], c["big"], html.escape(c["line"]), html.escape(src),
                        kind="highlight" if str(c["card"]) == "4" else ""))
st.caption("Each card shows the range across sources that disagree. Every figure, with its source and "
           "date, is on the Under the hood page.")

# ---------- where to look first ----------
st.subheader("Where to look first")
d = sc.assign(name=sc.state.map(names))
# five equal-sized groups of states by total score (equal weights): lowest -> highest
d["group"] = pd.qcut(d.score_total.rank(method="first"), 5, labels=False)
scale = [[edge / 5, c] for k, c in enumerate(cs.MAP_SCALE) for edge in (k, k + 1)]  # discrete steps

left, right = st.columns([2.2, 1], gap="large")
with left:
    fig = go.Figure(go.Choropleth(
        geojson=ui.geojson(), featureidkey="properties.state", locations=d.state, z=d.group,
        zmin=-0.5, zmax=4.5, colorscale=scale, showscale=False, marker_line_color="white", marker_line_width=0.8,
        customdata=d[["name", "score_need", "score_supply_gap", "score_ability_to_pay", "score_total"]],
        hovertemplate=("<b>%{customdata[0]}</b><br>Need %{customdata[1]:.0f} · Supply gap %{customdata[2]:.0f}"
                       " · Ability to pay %{customdata[3]:.0f}<br>Score %{customdata[4]:.0f} of 100<extra></extra>")))
    sel = d[d.state == st.session_state.sel_state]
    fig.add_trace(go.Choropleth(
        geojson=ui.geojson(), featureidkey="properties.state", locations=sel.state, z=[1],
        colorscale=[[0, cs.ORANGE], [1, cs.ORANGE]], showscale=False, marker_line_color="white",
        marker_line_width=1.5, customdata=sel[["name", "score_need", "score_supply_gap", "score_ability_to_pay",
                                                 "score_total"]],
        hovertemplate=("<b>%{customdata[0]}</b> (selected)<br>Need %{customdata[1]:.0f} · Supply gap "
                       "%{customdata[2]:.0f} · Ability to pay %{customdata[3]:.0f}<br>Score %{customdata[4]:.0f}"
                       " of 100<extra></extra>")))
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="white")
    fig.update_layout(height=430, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="white", dragmode=False,
                      hoverlabel=dict(bgcolor="white", font_color=cs.NAVY), clickmode="event+select")
    event = st.plotly_chart(fig, width="stretch", key="home_map", on_select="rerun", selection_mode="points",
                            config={"displayModeBar": False, "scrollZoom": False})
    pts = (event or {}).get("selection", {}).get("points", []) if event else []
    clicked = pts[0].get("location") if pts else None
    if clicked and clicked != st.session_state.get("last_map_click"):
        st.session_state.last_map_click = clicked
        st.session_state.sel_state = clicked
        st.rerun()

    lg, pick = st.columns([1.6, 1])
    with lg:
        swatches = "".join(f'<span style="display:inline-block;width:22px;height:12px;background:{c}"></span>'
                           for c in cs.MAP_SCALE)
        st.html(f'<div class="small-grey" style="margin-top:30px">Lower score {swatches} Higher score '
                f'&nbsp;&nbsp;<span style="display:inline-block;width:14px;height:12px;background:{cs.ORANGE}">'
                f'</span> Selected</div><div class="small-grey">Colour = equal-weight scorecard, in five '
                f'equal-sized groups of states. {ui.SCREENING}</div>')
    with pick:
        states = sorted(d.state, key=lambda s: names[s])

        def _pick():
            st.session_state.sel_state = st.session_state.home_pick

        st.session_state.home_pick = st.session_state.sel_state
        st.selectbox("Choose a state", states, key="home_pick", format_func=names.get, on_change=_pick)

with right:
    s = d[d.state == st.session_state.sel_state].iloc[0]
    r = reg.loc[s.state]
    with st.container(key="panel_home_state"):
        st.markdown(f"#### {names[s.state]}")
        st.html(f'<div class="small-grey">Rank {s['rank']} of 37 · score {s.score_total:.0f} of 100 '
                f'(equal weights)</div>' + ui.bar_rows([
                    ("Need", s.score_need, 100, cs.DARK_GREEN),
                    ("Supply gap", s.score_supply_gap, 100, cs.GREEN),
                    ("Ability to pay", s.score_ability_to_pay, 100, cs.MID_GREEN)]))
        n_fac = int(r.n_facilities)
        work = {"yes": "a public unit is reported working",
                "reported not working": "the only reports say public units aren't working",
                "unknown": "no evidence on whether a public unit is working"}[r.public_dialysis_working]
        st.html(f'<div style="margin-top:12px;font-size:.92rem"><b>{n_fac}</b> named dialysis '
                f'{"facility" if n_fac == 1 else "facilities"} in the register; {work}.</div>'
                f'<div style="font-size:.92rem;margin-top:6px">Main gap type in the evidence: '
                f'<b>{story.main_gap_type(r)}</b> ({int(r.n_rows)} register rows, '
                f'{int(r.gap_unknown)} with no stated cause).</div>')
        if s.state == halima["state"]:
            st.html('<div class="orange-line" style="margin-top:8px;font-size:.9rem">Halima\'s state</div>')
        if st.button("See the full scorecard", key="goto_scorecard", type="primary", width="stretch"):
            st.switch_page("views/scorecard.py")
st.html(f"<style>.st-key-goto_scorecard button {{ background:{cs.NAVY}; border-color:{cs.NAVY}; }}</style>")

# ---------- the story in six steps ----------
st.subheader("The story in six steps")
steps = [("The patient", "What does one dialysis session cost Halima's family?", "cost.py"),
         ("The gap", "Which states have the fewest hospitals per person?", "explorer.py"),
         ("The cause", "Is the gap equipment, workforce or systems?", "gaps.py"),
         ("Who pays", "Where need is high, can people pay?", "scorecard.py"),
         ("What a centre could do", "Patients treated and capacity used by one centre", "centre.py"),
         ("The honest limits", "Where the data is thin, and where sources disagree", "under_hood.py")]
for i, (title, q, page) in enumerate(steps):
    if i % 3 == 0:
        grid = st.columns(3)   # one row of three at a time, so phones stack them in order 1-6
    with grid[i % 3]:
        with st.container(border=True):
            st.html(f'<span class="step-num">{i + 1}</span>&nbsp; <b>{title}</b>'
                    f'<div class="small-grey" style="margin-top:4px">{q}</div>')
            st.page_link(f"views/{page}", label="Open →")

ui.footer("GRID3 · GRID3/WorldPop · NDHS 2024 · kidney register · sources on each card; "
          "boundaries: geoBoundaries (GRID3), CC BY 4.0",
          ui.data_as_of("grid3_hf_v2", "ndhs2024_api"))
