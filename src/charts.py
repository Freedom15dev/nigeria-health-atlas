"""Chart builders shared by notebooks, the PNG export and the app.
Each returns a Plotly figure in house style. Titles are built from the data."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from chart_style import (DARK_GREEN, GAP_COLOURS, GREEN, GRID, MID_GREEN, MUTED, NAVY, ORANGE, PALE_GREEN,
                         label_extremes, style)
from scoring import LABEL, PILLAR_NAMES, TOP_N

PILLAR_COLOURS = {"need": DARK_GREEN, "supply_gap": GREEN, "ability_to_pay": PALE_GREEN}
SRC_FAC = "GRID3 NGA Health Facilities v2.0; GRID3/WorldPop population v3.0"
SRC_SCORE = "GRID3 v2.0; GRID3/WorldPop v3.0; NDHS 2024 (DHS API and FR395)"


def short(name: str) -> str:
    return "FCT" if name == "Federal Capital Territory" else name


def spearman(df: pd.DataFrame, a: str, b: str) -> float:
    return df[[a, b]].corr(method="spearman").iloc[0, 1]


def link_words(r: float, a: str, b: str) -> str:
    if r >= 0.3:
        return f"States with more {a} also tend to have more {b}"
    if r <= -0.3:
        return f"States with more {a} tend to have less {b}"
    return f"No clear link between {a} and {b}"


# ---------- chart 1 ----------

def facilities_per_100k(panel: pd.DataFrame, highlight: list[str] | None = None) -> go.Figure:
    d = panel.sort_values("fac_sec_tert_per_100k")
    low, high = d.iloc[0], d.iloc[-1]
    ratio = (high.fac_sec_tert_grid3 / high.population_total) / (low.fac_sec_tert_grid3 / low.population_total)
    hl = highlight if highlight is not None else d.state.head(5).tolist()
    fig = go.Figure(go.Bar(
        x=d.fac_sec_tert_per_100k, y=d.state.map(short), orientation="h",
        marker_color=[ORANGE if s in hl else GREEN for s in d.state],
        text=d.fac_sec_tert_per_100k.map("{:.1f}".format), textposition="outside",
        textfont=dict(size=11, color=NAVY), cliponaxis=False,
        hovertemplate="%{y}: %{x:.1f} per 100,000<extra></extra>"))
    style(fig, title=f"{high.state} has about {ratio:.0f}x as many hospitals per person as {low.state}",
          subtitle="Secondary and tertiary health facilities per 100,000 people (lowest five in orange)",
          source=SRC_FAC, height=950, x_title="Facilities per 100,000 people", x_grid=True)
    return fig


# ---------- chart 2: the tension ----------

def tension_scatter(sc: pd.DataFrame, x: str, x_label: str, x_words: str) -> go.Figure:
    """One dot per state: a pillar score (x) against ability to pay (y), with 50-line quadrants."""
    r = spearman(sc, x, "score_ability_to_pay")
    d = sc.assign(name=sc.state.map(short))
    fig = go.Figure(go.Scatter(
        x=d[x], y=d.score_ability_to_pay, mode="markers+text",
        text=label_extremes(d, x, "score_ability_to_pay", name="name", n=3), textposition="top center",
        textfont=dict(size=11, color=NAVY), hovertext=d.name,
        marker=dict(size=10, color=GREEN, opacity=0.85),
        hovertemplate="%{hovertext}<br>" + x_label + " %{x:.0f}<br>Ability to pay %{y:.0f}<extra></extra>"))
    for v, axis in [(50, "x"), (50, "y")]:
        (fig.add_vline if axis == "x" else fig.add_hline)(v, line_dash="dot", line_color=MUTED, line_width=1)
    fig.add_shape(type="rect", x0=50, x1=103, y0=-3, y1=50, fillcolor=ORANGE, opacity=0.07,
                  line_width=0, layer="below")
    style(fig, title=f"{link_words(r, x_words, 'ability to pay')} (rank correlation {r:.2f})",
          subtitle=(f"{x_label} score vs ability-to-pay score (0–100 percentile ranks), one dot per state. "
                    f"Shaded: high {x_label.lower()}, low ability to pay.<br>{LABEL}"),
          source=SRC_SCORE, height=620, x_title=f"{x_label} score (0–100)", y_title="Ability-to-pay score (0–100)")
    fig.update_xaxes(range=[-3, 103]); fig.update_yaxes(range=[-3, 108])
    return fig


def need_vs_pay(sc: pd.DataFrame) -> go.Figure:
    return tension_scatter(sc, "score_need", "Need", "need")


def gap_vs_pay(sc: pd.DataFrame) -> go.Figure:
    return tension_scatter(sc, "score_supply_gap", "Supply gap", "hospital gap")


# ---------- chart 3: both ends of the scorecard ----------

def scorecard_ends(sc: pd.DataFrame, n: int = 5) -> go.Figure:
    top, bottom = sc.head(n), sc.tail(n)
    fig = make_subplots(rows=1, cols=2, shared_xaxes=True, horizontal_spacing=0.14,
                        subplot_titles=(f"Top {n}", f"Bottom {n}"))
    for col, d in enumerate([top, bottom], start=1):
        names = [f"{short(s)} (#{r})" for s, r in zip(d.state, d["rank"])]
        for pillar, colour in PILLAR_COLOURS.items():
            fig.add_trace(go.Bar(
                y=names, x=d[f"score_{pillar}"], orientation="h", name=PILLAR_NAMES[pillar],
                marker_color=colour, showlegend=(col == 1), legendgroup=pillar,
                hovertemplate="%{y}<br>" + PILLAR_NAMES[pillar] + ": %{x:.0f}<extra></extra>"), row=1, col=col)
        fig.add_trace(go.Scatter(
            y=names, x=d.score_total, mode="markers", name="Total (equal weights)",
            marker=dict(symbol="line-ns-open", size=22, color=NAVY, line_width=3),
            showlegend=(col == 1), legendgroup="total",
            hovertemplate="%{y}<br>Total: %{x:.0f}<extra></extra>"), row=1, col=col)
        fig.update_yaxes(autorange="reversed", row=1, col=col)
    fig.update_layout(barmode="group", bargap=0.25, showlegend=True,
                      legend=dict(orientation="h", y=1.16, x=0, title=None))
    style(fig, title=f"{top.state.iloc[0]} tops the equal-weight scorecard; {bottom.state.iloc[-1]} is last",
          subtitle=f"Pillar scores (0–100) for the top and bottom {n} states; navy tick = total.<br>{LABEL}",
          source=SRC_SCORE, height=620, x_grid=True)
    fig.update_layout(margin=dict(t=170))
    fig.update_xaxes(range=[0, 105], title_text="Score (0–100)")
    return fig


# ---------- stress-test ----------

def stress_chart(st: pd.DataFrame) -> go.Figure:
    share = f"share_in_top{TOP_N}_pct"
    d = st[st[share] > 0].sort_values(share)
    robust = (d[share] >= 80).sum()
    fig = go.Figure(go.Bar(
        x=d[share], y=d.state.map(short), orientation="h",
        marker_color=[GREEN if v >= 80 else PALE_GREEN for v in d[share]],
        text=[f"{v:.0f}%  (ranks {b}–{w})" for v, b, w in zip(d[share], d.best_rank, d.worst_rank)],
        textposition="outside", cliponaxis=False, textfont=dict(size=11, color=NAVY),
        hovertemplate="%{y}: in the top " + str(TOP_N) + " under %{x:.0f}% of weightings<extra></extra>"))
    fig.add_vline(80, line_dash="dot", line_color=MUTED, line_width=1)
    style(fig, title=f"{robust} states stay in the top {TOP_N} under at least 80% of weightings",
          subtitle=(f"Share of {int(st.n_weightings.iloc[0])} weightings (each pillar 0.2–0.5) that keep a state "
                    f"in the top {TOP_N}; best–worst rank in brackets.<br>States never in the top {TOP_N} are not shown. {LABEL}"),
          source=SRC_SCORE, height=560, x_title=f"% of weightings in the top {TOP_N}", x_grid=True)
    fig.update_xaxes(range=[0, 125], tickvals=[0, 20, 40, 60, 80, 100], ticksuffix="%")
    return fig


# ---------- chart 4: the kidney register ----------

SRC_REG = "Kidney register (news, government and peer-reviewed sources, 2010–2026; see data/register)"


def register_gap_types(by_state: pd.DataFrame) -> go.Figure:
    d = by_state.assign(total=by_state.n_rows).sort_values("total")
    known = int(d[["gap_equipment", "gap_workforce", "gap_systems"]].sum().sum())
    total = int(d.total.sum())
    top_gap = d[["gap_equipment", "gap_workforce", "gap_systems"]].sum().idxmax().replace("gap_", "")
    fig = go.Figure()
    for g, colour in GAP_COLOURS.items():
        fig.add_trace(go.Bar(y=d.state.map(short), x=d[f"gap_{g}"], orientation="h", name=g.capitalize(),
                             marker_color=colour,
                             hovertemplate="%{y}: %{x} " + g + " facts<extra></extra>"))
    fig.update_layout(barmode="stack", showlegend=True,
                      legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0, title=None, traceorder="normal"))
    style(fig, title=f"Only {known} of {total} state facts say what the gap is; {top_gap} problems come up most",
          subtitle="Kidney register: facts per state, coloured by the gap type the source states "
                   "(equipment, workforce, systems), grey = source doesn't say",
          source=SRC_REG, height=950, x_title="Register facts (one per source)", x_grid=True)
    fig.update_layout(margin=dict(t=135))
    return fig


def register_machines_per_million(by_state: pd.DataFrame, panel: pd.DataFrame) -> go.Figure:
    d = by_state.merge(panel[["state", "population_total"]], on="state")
    has = d.dropna(subset=["machines_working_high"]).copy()
    per_m = 1_000_000 / has.population_total
    has["low"], has["high"] = has.machines_working_low * per_m, has.machines_working_high * per_m
    has = has.sort_values("high")
    missing = len(d) - len(has)
    fig = go.Figure()
    for _, r in has.iterrows():
        fig.add_trace(go.Scatter(x=[r.low, r.high], y=[short(r.state)] * 2, mode="lines",
                                 line=dict(color=GREEN, width=6), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=has.high, y=has.state.map(short), mode="markers+text", marker=dict(color=GREEN, size=11),
        text=[(f"{lo:.0f}–{hi:.0f}" if lo != hi else f"{hi:.0f}") + (" machine" if hi == 1 else " machines")
              + f" ({e[:4]}–{l[:4]})"
              for lo, hi, e, l in zip(has.machines_working_low, has.machines_working_high,
                                      has.earliest_source_date, has.latest_source_date)],
        textposition="middle right", textfont=dict(size=11, color=MUTED), cliponaxis=False, showlegend=False,
        hovertemplate="%{y}: up to %{x:.1f} working machines per million people<extra></extra>"))
    style(fig, title=f"Where any count exists, it's under {np.ceil(has.high.max()):.0f} working machines per million people; "
                     f"{missing} states have no count at all",
          subtitle="Working dialysis machines reported in the register, per million people (line = range across sources). "
                   "Counts are a floor:<br>sources name some hospitals, not all. Years in brackets are the oldest and newest source.",
          source=SRC_REG + "; GRID3/WorldPop population v3.0", height=620,
          x_title="Working machines per million people", x_grid=True)
    fig.update_xaxes(range=[0, has.high.max() * 1.9])
    return fig


def machines_per_million_bars(by_state: pd.DataFrame, panel: pd.DataFrame) -> go.Figure:
    """Compact version for the app: horizontal bars, lowest first, upper end of the reported range."""
    d = by_state.merge(panel[["state", "population_total"]], on="state")
    has = d.dropna(subset=["machines_working_high"]).copy()
    has["high"] = has.machines_working_high / has.population_total * 1e6
    has["low"] = has.machines_working_low / has.population_total * 1e6
    has = has.sort_values("high", ascending=False)
    fig = go.Figure(go.Bar(
        x=has.high, y=has.state.map(short), orientation="h", marker_color=GREEN,
        text=[f"{h:.1f}" for h in has.high], textposition="outside", cliponaxis=False,
        customdata=has[["machines_working_low", "machines_working_high", "earliest_source_date", "latest_source_date"]],
        hovertemplate=("%{y}: %{x:.1f} per million<br>%{customdata[0]:.0f}–%{customdata[1]:.0f} working machines "
                       "named<br>sources %{customdata[2]} to %{customdata[3]}<extra></extra>")))
    style(fig, title=f"{len(has)} states have a count; {len(d) - len(has)} have none",
          subtitle="Working machines per million people (top of the range).<br>"
                   "A floor: sources name some hospitals, not all.",
          source="Kidney register; GRID3/WorldPop v3.0", height=520, x_grid=True)
    return fig


SOURCE_LABELS = {"guardian.ng": "NAN past president, via The Guardian", "pmc.ncbi.nlm.nih.gov": "Kidney360 study",
                 "www.gov.uk": "EUAA, via UK Home Office", "nigeriahealthwatch.com": "Nigeria Health Watch"}


def national_counts(national: pd.DataFrame) -> go.Figure:
    """The national counts that disagree, by measure: one bar per distinct figure, with source and year."""
    n = national[national["count"].astype(str).str.strip() != ""].copy()
    n["n"] = n["count"].astype(float)
    n["who"] = n.source_url.str.extract(r"https?://([^/]+)/")[0].map(SOURCE_LABELS).fillna("other")
    groups = {
        "Dialysis centres": n.item.eq("dialysis centre") & n.ownership.eq("mixed"),
        "Dialysis machines": n.item.eq("dialysis machine"),
        "Nephrologists": n.item.eq("nephrologist"),
    }
    fig = make_subplots(rows=3, cols=1, subplot_titles=list(groups), vertical_spacing=0.12)
    spreads = []
    for row, (label, mask) in enumerate(groups.items(), start=1):
        # one bar per distinct figure; a figure repeated by a later source keeps its earliest, working-status row
        g = (n[mask].sort_values(["status", "source_date"], key=lambda c: c.ne("working") if c.name == "status" else c)
                    .drop_duplicates("n").sort_values("n"))
        spreads.append(g.n.max() / g.n.min())
        labels = [f"{w}, {d[:4]}" for w, d in zip(g.who, g.source_date)]
        # the same source can publish two different figures: tell them apart
        labels = [f"{lab} ({'working' if st == 'working' else 'all'})" if labels.count(lab) > 1 else lab
                  for lab, st in zip(labels, g.status)]
        fig.add_trace(go.Bar(
            y=labels, x=g.n, orientation="h",
            marker_color=[GREEN if st == "working" else PALE_GREEN for st in g.status],
            text=[f"{v:,.0f}" + (" working" if st == "working" else "") for v, st in zip(g.n, g.status)],
            textposition="outside", cliponaxis=False, textfont=dict(size=11, color=NAVY),
            hovertemplate="%{x:,.0f}<br>%{y}<extra></extra>"), row=row, col=1)
        fig.update_xaxes(range=[0, g.n.max() * 1.3], row=row, col=1)
    style(fig, title=f"Published national counts differ by up to {max(spreads):.1f}x",
          subtitle="One bar per distinct published figure. Dark = counts working units only; light = doesn't say.<br>"
                   "The spread is why the 'Assess' step has to happen on the ground.",
          source="NAN past president via The Guardian; Kidney360 2022; EUAA via UK Home Office; Nigeria Health Watch",
          height=720, x_grid=True)
    fig.update_yaxes(showgrid=False)
    return fig


# ---------- chart 5: three (plus one) out-of-pocket figures ----------

def oop_table(hf: pd.DataFrame, wdi: pd.DataFrame) -> pd.DataFrame:
    """The published out-of-pocket shares side by side: the three quoted figures (headline card 1)
    plus the World Bank WDI series' latest year. One row per figure, with what it measures."""
    h = hf[(hf.card.astype(str) == "1") & (hf.role == "main")]
    rows = [{"figure": float(r.figure), "who": r.source_short, "date": r.source_date,
             "measures": ("share of total health expenditure, 2024" if "NHA" in r.source_short else
                          "share of total health spending; year and method not stated"),
             "qualifier": r.qualifier, "url": r.url} for r in h.itertuples()]
    o = wdi[wdi.indicator_id == "SH.XPD.OOPC.CH.ZS"].sort_values("year").iloc[-1]
    rows.append({"figure": float(o.value), "who": "World Bank WDI (API)", "date": str(int(o.year)),
                 "measures": f"share of current health expenditure, {int(o.year)}", "qualifier": "",
                 "url": "https://api.worldbank.org/v2/country/NGA/indicator/SH.XPD.OOPC.CH.ZS"})
    return pd.DataFrame(rows).sort_values("figure").reset_index(drop=True)


def oop_figures(hf: pd.DataFrame, wdi: pd.DataFrame) -> go.Figure:
    t = oop_table(hf, wdi)
    labels = [f"{w} ({d[:7]})" for w, d in zip(t.who, t.date)]
    fig = go.Figure(go.Bar(
        x=t.figure, y=labels, orientation="h", marker_color=GREEN,
        text=[f"{'almost ' if q == 'almost' else ''}{v:.0f}%" for v, q in zip(t.figure, t.qualifier)],
        textposition="outside", cliponaxis=False, textfont=dict(size=12, color=NAVY),
        customdata=t.measures, hovertemplate="%{y}: %{x:.1f}%<br>%{customdata}<extra></extra>"))
    style(fig, title=f"Published figures for the out-of-pocket share run from {t.figure.min():.0f}% to "
                     f"{t.figure.max():.0f}%",
          subtitle="Share of health spending paid by households at the point of care, as published. National only.<br>"
                   "They differ in year, method and what counts as health spending (total vs current).",
          source="NHA 2023–24 via The Gazette; Premium Times; Nairametrics; World Bank WDI", height=420,
          x_title="% of health spending paid out of pocket", x_grid=True)
    fig.update_xaxes(range=[0, 100])
    return fig


# ---------- chart 6: the centre model ----------

SRC_MODEL = "Illustrative centre model (config/assumptions_kidney.yaml); prices from the kidney register; World Bank exchange rate"
SCENARIO_NAMES = {"low": "Low (pessimistic)", "base": "Base", "high": "High (optimistic)"}
SHOCK_COLOURS = {0.0: DARK_GREEN, 0.2: GREEN, 0.5: PALE_GREEN}


def centre_scenarios(sc: pd.DataFrame) -> go.Figure:
    """Left: patients treated per scenario. Right: break-even price vs price received,
    at today's exchange rate and with the naira 20% and 50% weaker."""
    base = sc[(sc.scenario == "base") & (sc.naira_shock == 0)].iloc[0]
    order = ["low", "base", "high"]
    fig = make_subplots(rows=1, cols=2, column_widths=[0.32, 0.68], horizontal_spacing=0.14,
                        subplot_titles=("Patients treated (people on the programme)",
                                        "Break-even price per session vs price received (N)"))
    today = sc[sc.naira_shock == 0].set_index("scenario").loc[order]
    fig.add_trace(go.Bar(x=[SCENARIO_NAMES[s] for s in order], y=today.patients_treated, marker_color=GREEN,
                         text=[f"{p:.0f}<br>({s:,.0f} sessions/yr)" for p, s in zip(today.patients_treated,
                                                                                   today.sessions_per_year)],
                         textposition="outside", cliponaxis=False, showlegend=False,
                         hovertemplate="%{x}: %{y:.0f} patients<extra></extra>"), row=1, col=1)
    for shock, colour in SHOCK_COLOURS.items():
        d = sc[sc.naira_shock == shock].set_index("scenario").loc[order]
        name = "Break-even, today's exchange rate" if shock == 0 else f"Break-even, naira {shock:.0%} weaker"
        fig.add_trace(go.Bar(x=[SCENARIO_NAMES[s] for s in order], y=d.breakeven_price_ngn, name=name,
                             marker_color=colour, hovertemplate="%{x}: N%{y:,.0f}<extra>" + name + "</extra>"),
                      row=1, col=2)
    fig.add_trace(go.Scatter(x=[SCENARIO_NAMES[s] for s in order], y=today.average_price_ngn,
                             mode="markers+text", name="Price received (average across payers)",
                             marker=dict(symbol="line-ew-open", size=46, color=NAVY, line_width=3),
                             text=[f"N{p:,.0f}" for p in today.average_price_ngn], textposition="top center",
                             textfont=dict(size=11, color=NAVY), cliponaxis=False,
                             hovertemplate="%{x}: N%{y:,.0f} received<extra></extra>"), row=1, col=2)
    fig.update_layout(barmode="group", showlegend=True,
                      legend=dict(orientation="h", y=-0.2, x=0.25, title=None, font=dict(size=11)))
    gap = base.breakeven_price_ngn - base.average_price_ngn
    title = (f"In the base case, a session costs N{base.breakeven_price_ngn:,.0f} to break even but brings in "
             f"N{base.average_price_ngn:,.0f}" if gap > 0 else
             f"In the base case, the centre breaks even at N{base.breakeven_price_ngn:,.0f} a session, "
             f"below the N{base.average_price_ngn:,.0f} it receives")
    style(fig, title=title,
          subtitle=("One illustrative haemodialysis centre, low / base / high scenarios; break-even rises as the "
                    "naira weakens because consumables and machines are imported.<br>"
                    "An illustrative model using public data and stated assumptions. Not investment advice."),
          source=SRC_MODEL, height=640)
    fig.update_layout(margin=dict(b=170))
    fig.layout.annotations[-1].update(yshift=-120)  # source line below the legend
    fig.update_yaxes(rangemode="tozero")
    fig.update_yaxes(range=[0, today.patients_treated.max() * 1.35], row=1, col=1)
    fig.update_yaxes(tickprefix="N", row=1, col=2)
    return fig


def centre_sensitivity(sens: pd.DataFrame, top: int = 10) -> go.Figure:
    """Tornado: yearly net cash when each input moves to its low and high bound (others at base)."""
    d = sens.head(top).iloc[::-1]
    base = d.base_net_cash_ngn.iloc[0]
    nice = lambda i: (i.replace("_ngn", "").replace("_usd", " (US$)").replace("_pct_of", " % of")
                       .replace("_", " ").capitalize())
    labels = [f"{nice(i)}{'' if v else ' *'}" for i, v in zip(d.input, d.verified)]
    fig = go.Figure()
    for bound, colour, name in [("low", PALE_GREEN, "Input at its low value"), ("high", GREEN, "Input at its high value")]:
        fig.add_trace(go.Bar(y=labels, x=(d[f"net_cash_at_{bound}_ngn"] - base) / 1e6, base=base / 1e6,
                             orientation="h", name=name, marker_color=colour,
                             customdata=d[f"{bound}_value"],
                             hovertemplate="%{y}<br>at %{customdata}: N%{x:,.0f}m a year<extra></extra>"))
    fig.add_vline(base / 1e6, line_color=NAVY, line_width=1)
    fig.add_vline(0, line_dash="dot", line_color=MUTED, line_width=1)
    first = d.iloc[-1]
    style(fig, title=f"The imported consumables cost moves the result most, and it's an unverified assumption"
          if first.input == "consumables_per_session_usd" and not first.verified else
          f"{first.input.replace('_', ' ').capitalize()} moves the result most",
          subtitle=("Yearly net cash (N million) when one input moves to its low or high value, all else at base "
                    f"(solid line = base, {'−' if base < 0 else ''}N{abs(base) / 1e6:,.0f}m; dotted = break-even).<br>* = assumption to verify, "
                    "no public source found."),
          source=SRC_MODEL, height=560, x_title="Net cash per year (N million)", x_grid=True)
    fig.update_layout(barmode="overlay", showlegend=True, legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, title=None))
    fig.update_layout(margin=dict(t=150))
    return fig
