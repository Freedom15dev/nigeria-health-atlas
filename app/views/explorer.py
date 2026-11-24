"""Page 2: State explorer. A BI-style dashboard: filter bar, KPI tiles, bar chart, side cards, table."""
import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import chart_style as cs
import components as ui
import story
from register_summary import summarise_by_state

ui.setup(bi=True)
names = ui.display_names()
panel = ui.csv("state_panel.csv")
sc = ui.csv("scorecard.csv")[["state", "score_total", "rank"]]
fc = ui.csv("facility_counts.csv")
ZONES = sorted(panel.zone.unique())
LEVELS = ["Primary", "Secondary", "Tertiary"]
DEFAULTS = {"ex_zone": "All zones", "ex_state": "All states", "ex_spec": "Kidney",
            "ex_own": ["Public", "Private"], "ex_lvl": ["Secondary", "Tertiary"]}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def reset():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


# ---------- filter bar ----------
head_l, head_r = st.columns([4, 1], vertical_alignment="bottom")
with head_l:
    st.title("State explorer")
    st.markdown("How many hospitals, how much specialist capacity, and how much ability to pay, state by state.")
download_slot = head_r.empty()

with st.container(key="white_filters"):
    f = st.columns([1.2, 1.3, 1.3, 1.3, 1.9, 0.8], vertical_alignment="bottom")
    zone = f[0].selectbox("Zone", ["All zones", *ZONES], key="ex_zone")
    in_zone = panel if zone == "All zones" else panel[panel.zone == zone]
    options = ["All states", *sorted(in_zone.state, key=names.get)]
    if st.session_state.ex_state not in options:
        st.session_state.ex_state = "All states"
    state = f[1].selectbox("State", options, key="ex_state", format_func=lambda s: names.get(s, s))
    spec = f[2].segmented_control("Specialty", ["Kidney", "Cancer"], key="ex_spec") or "Kidney"
    own = f[3].pills("Ownership", ["Public", "Private"], selection_mode="multi", key="ex_own")
    lvl = f[4].pills("Facility level", LEVELS, selection_mode="multi", key="ex_lvl")
    f[5].button("Reset filters", on_click=reset, type="tertiary")

notes = []
if not own:
    own, _ = ["Public", "Private"], notes.append("No ownership picked, so both are shown.")
if not lvl:
    lvl, _ = LEVELS, notes.append("No facility level picked, so all levels are shown.")
own_l, lvl_l = [o.lower() for o in own], [v.lower() for v in lvl]
both_owners = set(own_l) == {"public", "private"}
own_keep = own_l + (["unknown"] if both_owners else [])          # facilities
reg_own_keep = own_l + (["mixed", "unknown"] if both_owners else [])  # register rows
view_states = list(in_zone.state)
selected = None if state == "All states" else state
focus = [selected] if selected else view_states

# ---------- numbers (all from processed tables) ----------
fac_f = fc[fc.level.isin(lvl_l) & fc.ownership.isin(own_keep)]
fac_state = fac_f.groupby("state").facilities.sum().reindex(panel.state, fill_value=0)
pop = panel.set_index("state").population_total
per100k = fac_state / pop * 1e5
national = fac_state.sum() / pop.sum() * 1e5

specialty = "cancer" if spec == "Cancer" else "kidney"
reg_rows = ui.csv(f"register_{specialty}_rows.csv", dtype=str, keep_default_na=False)
reg_f = reg_rows[reg_rows.ownership.isin(reg_own_keep)]
by_state = summarise_by_state(reg_f, list(panel.state), specialty).set_index("state")
machine_word = "radiotherapy" if spec == "Cancer" else "dialysis"
ins = panel.set_index("state")[["insurance_any_women_pct", "insurance_any_men_pct"]].mean(axis=1)
wealth = panel.set_index("state").wealth_top2_pct
w = pop[focus] / pop[focus].sum()          # population weights for a group of states
score = sc.set_index("state").score_total

table = pd.DataFrame({
    "State": [names[s] for s in view_states],
    "Zone": panel.set_index("state").zone[view_states].values,
    "Facilities per 100k": per100k[view_states].round(1).values,
    f"Working {machine_word} machines (register)": [
        "[—]" if pd.isna(by_state.loc[s].get("machines_working_low"))
        else (f"{by_state.loc[s].machines_working_low:.0f}" if by_state.loc[s].machines_working_low
              == by_state.loc[s].machines_working_high
              else f"{by_state.loc[s].machines_working_low:.0f}–{by_state.loc[s].machines_working_high:.0f}")
        for s in view_states],
    "Insured % (NDHS 2024)": ins[view_states].round(1).values,
    "Score (0–100)": score[view_states].values,
    "_state": view_states,
}).sort_values("Score (0–100)", ascending=False)
with download_slot:
    ui.download(table.drop(columns="_state"), "state_explorer.csv", key="dl_top")

# ---------- KPI row ----------
k = st.columns(5)
view_label = names[selected] if selected else (zone if zone != "All zones" else "Nigeria")
grp_rate = fac_state[focus].sum() / pop[focus].sum() * 1e5
delta = grp_rate - national
arrow = "▲" if delta >= 0 else "▼"
colour = cs.GOOD if delta >= 0 else cs.BAD
lo_m, hi_m, n_m = story.machines_range(by_state.loc[focus].reset_index())
if n_m == 0:
    machines_big, machines_line = "[—]", "No machine count in the register for this view"
else:
    machines_big = f"{lo_m:.0f}" if lo_m == hi_m else f"{lo_m:.0f}–{hi_m:.0f}"
    machines_line = f"in {n_m} of {len(focus)} states with a count; the rest: unknown"
tiles = [
    ("States in view", f"{len(view_states)}", html.escape(names[selected] + " selected" if selected else view_label)),
    ("Facilities per 100,000", f"{grp_rate:.1f}",
     "national average" if set(focus) == set(panel.state) else
     f'<span style="color:{colour}">{arrow} {abs(delta):.1f}</span> vs national {national:.1f}'),
    (f"Working {machine_word} machines", machines_big, machines_line),
    ("Health insurance (any)", f"{(ins[focus] * w).sum():.1f}%",
     "NDHS 2024, women and men" + (", population-weighted average of states" if len(focus) > 1 else "")),
    ("Scorecard", f"{score[focus].mean():.0f}/100" if len(focus) > 1 else f"{score[selected]:.0f}/100",
     ("average of states in view" if len(focus) > 1 else f"rank {int(sc.set_index('state')['rank'][selected])} "
      "of 37") + " · " + ui.SCREENING),
]
for col, (label, big, line) in zip(k, tiles):
    col.html(ui.card(label, big, line))
for n in notes:
    st.caption(n)

# ---------- main grid ----------
left, right = st.columns([8, 4], gap="medium")
d = pd.DataFrame({"state": view_states, "rate": per100k[view_states].values}).sort_values("rate", ascending=False)
colours = [cs.ORANGE if s == selected else (cs.PALE_GREEN if selected else cs.GREEN) for s in d.state]
fig = go.Figure(go.Bar(x=d.rate, y=d.state.map(names), orientation="h", marker_color=colours,
                       text=d.rate.map("{:.1f}".format), textposition="outside", cliponaxis=False,
                       hovertemplate="%{y}: %{x:.1f} per 100,000<extra></extra>"))
fig.add_vline(national, line_dash="dash", line_color=cs.NAVY, line_width=1.5,
              annotation_text=f"National {national:.1f}", annotation_position="top")
low = d.iloc[-1]
levels_txt = " + ".join(lvl).lower()
cs.style(fig, title=f"{names[low.state]} has the fewest {levels_txt} facilities per person"
         + (f" in the {zone}" if zone != "All zones" else ""),
         subtitle=f"Facilities per 100,000 people · {view_label} · {', '.join(own).lower()} "
                  f"(sorted lowest first; dashed line = national average)",
         source="GRID3 NGA Health Facilities v2.0; GRID3/WorldPop population v3.0",
         height=max(420, 26 * len(d) + 190), x_grid=True)
with left:
    with st.container(key="white_bar"):
        ui.chart(fig, key="ex_bar")
    st.caption("GRID3 calls its facility list non-exhaustive and non-validated, and per-100,000 rates use "
               "modelled population, so small differences between states don't mean much.")

with right:
    # 1. public vs private (level filter applies; ownership filter doesn't, so the split is visible)
    o = fc[fc.state.isin(focus) & fc.level.isin(lvl_l)].groupby("ownership").facilities.sum()
    pub, prv, unk = o.get("public", 0), o.get("private", 0), o.get("unknown", 0)
    donut = go.Figure(go.Pie(labels=["Public", "Private"], values=[pub, prv], hole=0.68, sort=False,
                             marker_colors=[cs.DARK_GREEN, cs.PALE_GREEN], textinfo="none",
                             hovertemplate="%{label}: %{value:,}<extra></extra>"))
    share = pub / (pub + prv) * 100 if pub + prv else float("nan")
    donut.update_layout(height=150, margin=dict(l=0, r=0, t=0, b=0), showlegend=False, paper_bgcolor="white",
                        annotations=[dict(text=f"<b>{share:.0f}%</b><br>public", showarrow=False,
                                          font=dict(size=14, color=cs.NAVY, family=cs.FONT))])
    with st.container(key="white_owner"):
        st.markdown("**Public vs private**")
        c1, c2 = st.columns([1, 1.2], vertical_alignment="center")
        with c1:
            ui.chart(donut, key="ex_donut")
        c2.html(f'<div class="small-grey">Public {pub:,}<br>Private {prv:,}<br>Ownership unknown {unk:,}</div>')
    # 2. level mix (ownership filter applies)
    lv = fc[fc.state.isin(focus) & fc.ownership.isin(own_keep)].groupby("level").facilities.sum()
    tot = lv[["primary", "secondary", "tertiary"]].sum()
    seg_c = {"primary": cs.PALE_GREEN, "secondary": cs.GREEN, "tertiary": cs.DARK_GREEN}
    bar = "".join(f'<div style="width:{lv[x] / tot * 100:.2f}%;background:{seg_c[x]}"></div>'
                  for x in seg_c) if tot else ""
    with st.container(key="white_levels"):
        st.markdown("**Facility level mix**")
        st.html(f'<div style="display:flex;height:14px;border-radius:7px;overflow:hidden">{bar}</div>'
                + "".join(f'<div class="bar-row"><div class="name"><span style="color:{seg_c[x]}">■</span> '
                          f'{x.title()}</div><div class="val" style="width:auto">{lv[x]:,} '
                          f'({lv[x] / tot * 100 if tot else 0:.0f}%)</div></div>' for x in seg_c))
    # 3. gap type from the register
    with st.container(key="white_gaps"):
        st.markdown(f"**{spec} care: gap type**")
        g = reg_f[reg_f.state.isin(focus)].gap_type.value_counts()
        if g.sum() == 0:
            st.html('<div class="small-grey">No register rows for this view: [—]. That means no evidence was '
                    'found, not that nothing is missing.</div>')
        else:
            gmax = max(g.max(), 1)
            st.html(ui.bar_rows([(t.title(), g.get(t, 0), gmax, cs.GAP_COLOURS[t]) for t in cs.GAP_COLOURS])
                    + f'<div class="small-grey">Register rows ({int(g.sum())}) by the cause the source '
                      f'gives; "unknown" = the source doesn\'t say.</div>')
    # 4. ability to pay
    with st.container(key="white_pay"):
        st.markdown("**Ability to pay**")
        st.html(ui.bar_rows([("Health insurance (any)", (ins[focus] * w).sum(), 100, cs.GREEN),
                             ("Top two wealth groups", (wealth[focus] * w).sum(), 100, cs.DARK_GREEN)])
                + '<div class="small-grey">% of people (insurance) and of households (wealth). NDHS 2024; '
                  'survey estimates with margins of error.</div>')

# ---------- states table ----------
st.subheader("States in view")
show = table.drop(columns="_state")


def _hl(row):
    on = selected and row["State"] == names.get(selected)
    return [f"background-color:{cs.ORANGE_BG};color:{cs.ORANGE_TEXT};font-weight:600" if on else ""] * len(row)


st.dataframe(show.style.apply(_hl, axis=1).format({"Facilities per 100k": "{:.1f}", "Insured % (NDHS 2024)": "{:.1f}",
                                                    "Score (0–100)": "{:.0f}"}),
             hide_index=True, width="stretch")
ui.download(show, "state_explorer.csv", key="dl_bottom")

ui.footer("GRID3 NGA Health Facilities v2.0 · GRID3/WorldPop population v3.0 · NDHS 2024 · kidney register",
          ui.data_as_of("grid3_hf_v2", "grid3_pop_v3", "ndhs2024_api"))
