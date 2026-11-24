"""Page 6: Cost pressure. Monthly naira rate, all-items prices and health prices; what the imported
part of one dialysis session costs in naira."""
import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import chart_style as cs
import components as ui
import story

ui.setup()
mp = ui.csv("monthly_prices.csv", parse_dates=["month"])
nbs = ui.csv("nbs_cpi_health.csv", parse_dates=["month"])
a = ui.assumptions()
cons_usd = a["costs"]["consumables_per_session_usd"]["value"]
d = mp[["month", "usd_ngn", "price_index"]].merge(nbs[["month", "health_index", "basket"]], on="month", how="outer") \
    .sort_values("month").reset_index(drop=True)
# end at the latest month both sources cover, so every card and line covers the same period
first, last = d.month.min().date(), min(mp.month.max(), nbs.month.max()).date()


def months_back(n: int) -> dt.date:
    m = pd.Timestamp(last) - pd.DateOffset(months=n)
    return max(m.date(), first)


st.session_state.setdefault("cp_range", (months_back(36), last))


def quick(n):
    st.session_state.cp_range = (months_back(n) if n else first, last)


ui.opening("Why does a weaker naira make dialysis dearer?",
           "Dialysers, bloodlines and machines are imported and priced in dollars, while patients pay in naira. "
           "When the naira weakens, the imported part of every session costs more, even if nothing else changes.")

with st.container(key="panel_dates"):
    c = st.columns([1.6, 0.4, 0.4, 0.4, 0.4], vertical_alignment="bottom")
    rng = c[0].date_input("From – To (monthly data)", key="cp_range", min_value=first, max_value=last,
                          format="YYYY-MM-DD")
    for col, (lab, n) in zip(c[1:], [("1Y", 12), ("3Y", 36), ("5Y", 60), ("All", 0)]):
        col.button(lab, on_click=quick, args=(n,), width="stretch", key=f"cp_{lab}")
if not isinstance(rng, (tuple, list)) or len(rng) != 2:
    st.info("Pick an end date too.")
    st.stop()
start, end = pd.Timestamp(rng[0]).to_period("M").to_timestamp(), pd.Timestamp(rng[1]).to_period("M").to_timestamp()
w = d[(d.month >= start) & (d.month <= end)]
if len(w) < 2:
    st.info("Pick a range of at least two months.")
    st.stop()

lines = st.pills("Lines", ["Naira per US$", "All prices (CPI)", "Health prices (CPI)"], selection_mode="multi",
                 default=["Naira per US$", "All prices (CPI)", "Health prices (CPI)"], key="cp_lines")


def indexed(col):
    s = w[["month", col]].dropna()
    return s.assign(v=s[col] / s[col].iloc[0] * 100) if len(s) else s.assign(v=[])


fx, cpi, hp = indexed("usd_ngn"), indexed("price_index"), indexed("health_index")
fig = go.Figure()
for name, s, colour in [("Naira per US$", fx, cs.ORANGE), ("All prices (CPI)", cpi, cs.GREEN),
                        ("Health prices (CPI)", hp, cs.NAVY)]:
    if name in (lines or []) and len(s):
        fig.add_trace(go.Scatter(x=s.month, y=s.v, name=name, mode="lines", line=dict(color=colour, width=2.5),
                                 hovertemplate="%{x|%b %Y}: %{y:.0f}<extra>" + name + "</extra>"))
fig.add_hline(100, line_color=cs.GRID, line_width=1)
fx_chg = fx.v.iloc[-1] - 100 if len(fx) else float("nan")
cpi_chg = cpi.v.iloc[-1] - 100 if len(cpi) else float("nan")
title = (f"From {start:%b %Y} to {fx.month.iloc[-1]:%b %Y}, a dollar came to cost {abs(fx_chg):.0f}% "
         f"{'more' if fx_chg >= 0 else 'less'} in naira; "
         f"prices overall {'rose' if cpi_chg >= 0 else 'fell'} {abs(cpi_chg):.0f}%")
cs.style(fig, title=title, subtitle=f"Index, start of the period = 100 · monthly",
         source="CBN (exchange rate, inflation) via Money Matters; NBS CPI (health)", height=480)
fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, title=None))
fig.update_layout(margin=dict(t=125))
ui.chart(fig, key="cp_chart")
notes = []
if len(hp) and hp.month.iloc[0] > start:
    notes.append(f"Health prices start in {hp.month.iloc[0]:%b %Y} (the first month in the NBS workbook), so that "
                 "line is indexed to its own first month.")
if len(hp) and (hp.month < pd.Timestamp(2025, 1, 1)).any() and (hp.month >= pd.Timestamp(2025, 1, 1)).any():
    notes.append("NBS changed the CPI basket in January 2025 (new items and weights); earlier months "
                 "are the old index rescaled by NBS, so the health line joins two baskets.")
notes.append("All prices = Money Matters' price index, rebuilt from CBN year-on-year inflation (an approximation, "
             "not NBS's own index).")
for n_ in notes:
    st.caption(n_)

# ---------- three cards ----------
c = st.columns(3)
if len(fx):
    f0, f1 = w.dropna(subset=["usd_ngn"]).usd_ngn.iloc[[0, -1]]
    c[0].html(ui.card("Naira per US$", f"₦{f0:,.0f} → ₦{f1:,.0f}",
                      f"{fx.month.iloc[0]:%b %Y} to {fx.month.iloc[-1]:%b %Y} (monthly average, CBN)"))
    c[2].html(ui.card("Imported part of one session", f"{story.naira(cons_usd * f0, True)} → {story.naira(cons_usd * f1, True)}",
                      f"US${cons_usd:,.0f} of consumables (centre-model assumption, to verify) at each month's rate. "
                      "This is what the Centre model's naira shock moves.", kind="highlight"))
if len(hp) >= 2:
    h = w.dropna(subset=["health_index"])
    c[1].html(ui.card("Health prices", f"{(h.health_index.iloc[-1] / h.health_index.iloc[0] - 1) * 100:+.0f}%",
                      f"{h.month.iloc[0]:%b %Y} to {h.month.iloc[-1]:%b %Y} (NBS CPI, health division)"))
else:
    c[1].html(ui.card("Health prices", "[—]", "NBS health prices start in "
                      f"{nbs.month.min():%b %Y}; pick a range after that."))

ui.download(w, "cost_pressure_monthly.csv")
ui.footer("CBN exchange rate and inflation (via Money Matters) · NBS CPI " + str(nbs.release.dropna().iloc[0])
          if nbs.release.notna().any() else "CBN via Money Matters · NBS CPI",
          f"naira and inflation to {mp.month.max():%b %Y}; health prices to {nbs.month.max():%b %Y}")
