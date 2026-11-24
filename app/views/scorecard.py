"""Page 3: Scorecard. Equal-weight ranking with both ends shown, a weight stress-test, and the
need-vs-ability-to-pay scatter. A screening tool, not investment advice."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import chart_style as cs
import components as ui
import scoring
import story

ui.setup()
names = ui.display_names()
panel = ui.csv("state_panel.csv")
stress = ui.csv("scorecard_stress.csv")
halima_state = story.halima()["state"]
PILLARS = list(scoring.PILLARS)
for p in PILLARS:
    st.session_state.setdefault(f"w_{p}", 33)


def reset():
    for p in PILLARS:
        st.session_state[f"w_{p}"] = 33


ui.opening("Which states need specialist care most, and can people pay for it?",
           "Each state gets three scores from 0 to 100: **need** (population, a stand-in until people aged 40+ "
           "are counted by state), **supply gap** (fewer hospitals per 100,000 people = bigger gap) and **ability to "
           "pay** (health insurance and household wealth). A score is a percentile rank: 100 = highest of the "
           "37 states, 0 = lowest, so one extreme state can't squash the rest.")
st.html(f'<div class="orange-line">{ui.SCREENING}</div>')

with st.container(key="panel_weights"):
    st.markdown("**Stress-test the weights**")
    c = st.columns([1, 1, 1, 0.6], vertical_alignment="bottom")
    raw = {p: c[i].slider(scoring.PILLAR_NAMES[p], 0, 100, key=f"w_{p}", format="%d") for i, p in enumerate(PILLARS)}
    c[3].button("Reset to equal", on_click=reset, width="stretch")
    if sum(raw.values()) == 0:
        st.warning("All three weights are zero, so equal weights are used.")
        raw = {p: 1 for p in PILLARS}
    w = scoring.normalise(raw)
    st.html('<div class="small-grey">Weights used (always add up to 100%): '
            + " · ".join(f"{scoring.PILLAR_NAMES[p]} <b>{w[p]:.0%}</b>" for p in PILLARS) + "</div>")

sc = scoring.build_scorecard(panel, w)
sc["State"] = sc.state.map(names)
cols = {"rank": "#", "State": "State", "score_need": "Need", "score_supply_gap": "Gap",
        "score_ability_to_pay": "Pay", "score_total": "Score"}


def ends_table(d: pd.DataFrame):
    t = d[list(cols)].rename(columns=cols)
    st.dataframe(t.style.format({c: "{:.0f}" for c in ["Need", "Gap", "Pay", "Score"]}), hide_index=True,
                 width="stretch")


left, right = st.columns(2, gap="large")
with left:
    st.markdown("**Top 5**")
    ends_table(sc.head(5))
with right:
    st.markdown("**Bottom 5**")
    ends_table(sc.tail(5))
equal = all(abs(v - 1 / 3) < 1e-9 for v in w.values())
st.caption(("Equal weights. " if equal else "Your weights. ") + "Ties share a rank. Never read the score without "
           "its three parts.")
ui.download(sc[["rank", "state", "zone", "score_need", "score_supply_gap", "score_ability_to_pay", "score_total",
                "label"]], "scorecard_with_your_weights.csv")

# ---------- need against ability to pay ----------
st.subheader("Need against ability to pay")
r = sc[["score_need", "score_ability_to_pay"]].corr(method="spearman").iloc[0, 1]
d = sc.assign(name=sc.state.map(names))
hl = d.state == halima_state
fig = go.Figure()
for x0, x1, y0, y1, fill, label in [
        (50, 100, 0, 50, cs.ORANGE_BG, "High need, low ability to pay:<br>where PPP financing and insurance matter most"),
        (50, 100, 50, 100, "#F7FAF8", "High need, more ability to pay"),
        (0, 50, 0, 50, "#FAFBFC", "Lower need, low ability to pay"),
        (0, 50, 50, 100, "#FAFBFC", "Lower need, more ability to pay")]:
    fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, fillcolor=fill, line_width=0, layer="below")
    fig.add_annotation(x=x0 + 1 if x0 == 0 else x1 - 1, y=y0 + 1 if y0 == 0 else y1 - 1, text=label,
                       showarrow=False, xanchor="left" if x0 == 0 else "right",
                       yanchor="bottom" if y0 == 0 else "top", align="left" if x0 == 0 else "right",
                       bgcolor="rgba(255,255,255,0.85)",
                       font=dict(size=11, color=cs.ORANGE_TEXT if fill == cs.ORANGE_BG else cs.TEXT2))
fig.add_trace(go.Scatter(x=d[~hl].score_need, y=d[~hl].score_ability_to_pay, mode="markers",
                         marker=dict(size=11, color=cs.GREEN, opacity=0.9, line=dict(color="white", width=1)),
                         hovertext=d[~hl].name,
                         hovertemplate="%{hovertext}<br>Need %{x:.0f} · Ability to pay %{y:.0f}<extra></extra>"))
fig.add_trace(go.Scatter(x=d[hl].score_need, y=d[hl].score_ability_to_pay, mode="markers+text",
                         marker=dict(size=15, color=cs.ORANGE, line=dict(color="white", width=1.5)),
                         text=[f"{n} (Halima)" for n in d[hl].name], textposition="middle right",
                         textfont=dict(color=cs.ORANGE_TEXT, size=12), hovertext=d[hl].name,
                         hovertemplate="%{hovertext}<br>Need %{x:.0f} · Ability to pay %{y:.0f}<extra></extra>"))
words = ("States with more need also tend to have more ability to pay" if r >= 0.3 else
         "States with more need tend to have less ability to pay" if r <= -0.3 else
         "No clear link between need and ability to pay")
cs.style(fig, title=f"{words} (rank correlation {r:.2f})",
         subtitle=f"Need score vs ability-to-pay score (0–100), one dot per state · {ui.SCREENING}",
         source="GRID3/WorldPop v3.0; NDHS 2024 (DHS API and FR395)", height=560,
         x_title="Need score (0–100)", y_title="Ability-to-pay score (0–100)")
fig.update_xaxes(range=[-2, 102], showgrid=False)
fig.update_yaxes(range=[-2, 102])
ui.chart(fig, key="sc_scatter")
n_q = int(((d.score_need >= 50) & (d.score_ability_to_pay < 50)).sum())
dx = scoring.build_scorecard(panel, w, scoring.PILLARS_NEED_WITH_DIAGNOSES)
r_dx = dx[["score_need", "score_ability_to_pay"]].corr(method="spearman").iloc[0, 1]
st.markdown(f"**{n_q} of 37 states** sit in the orange corner: high need, low ability to pay. "
            f"If self-reported high blood pressure and blood sugar are added to need, the rank correlation becomes "
            f"{r_dx:+.2f}, but those figures partly measure who gets tested (which rises with wealth), so they're "
            "kept out of the main score. Under the hood shows both versions.")

# ---------- stress test (pre-computed over the weight grid) ----------
st.subheader("Which states stay near the top whatever the weights?")
t = stress.copy()
n_w = int(t.n_weightings.iloc[0])
robust = t[t.share_in_top10_pct >= 80]
st.markdown(f"I re-ran the score {n_w} times, moving each weight from 20% to 50%. "
            f"**{len(robust)} states** are in the top 10 in at least 80% of those runs: "
            + ", ".join(names[s] for s in robust.state) + ".")
show = t.assign(State=t.state.map(names))[["State", "share_in_top10_pct", "best_rank", "worst_rank", "median_rank"]] \
    .rename(columns={"share_in_top10_pct": "% of weightings in top 10", "best_rank": "Best rank",
                     "worst_rank": "Worst rank", "median_rank": "Median rank"})
st.dataframe(show.head(15), hide_index=True, width="stretch")
ui.download(t, "scorecard_stress_test.csv")

ui.footer("GRID3 NGA Health Facilities v2.0 · GRID3/WorldPop population v3.0 · NDHS 2024 (DHS API, FR395)",
          ui.data_as_of("grid3_hf_v2", "grid3_pop_v3", "ndhs2024_api"))
