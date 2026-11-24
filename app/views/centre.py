"""Page 5: Centre model. One illustrative dialysis centre: patients treated, capacity used, break-even.
All maths is in src/centre_model.py; this page only collects inputs and shows results."""
import html

import streamlit as st

import centre_model as M
import chart_style as cs
import components as ui
import story

ui.setup()
a = ui.assumptions()
base = M.scenario_inputs(a, "base")
mix0 = {p: v["value"] for p, v in a["payer_mix"].items() if isinstance(v, dict)}
DEFAULTS = {
    "cm_machines": int(base["machines"]), "cm_shifts": int(base["shifts_per_day"]),
    "cm_days": int(base["days_open_per_week"]), "cm_used": int(round(base["capacity_used"] * 100)),
    "cm_spp": int(base["sessions_per_patient_per_week"]), "cm_price": int(base["price_out_of_pocket_ngn"]),
    "cm_sub": int(round(mix0["subsidised"] * 100)), "cm_nhia": int(round(mix0["nhia"] * 100)),
    "cm_hmo": int(round(mix0["employer_hmo"] * 100)), "cm_cons": float(base["consumables_per_session_usd"]),
    "cm_power": int(base["power_water_per_session_ngn"]), "cm_staff": int(base["staff_cost_per_shift_ngn"]),
    "cm_shock": "No shock", "cm_ppp": "Fee per session",
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)
specs = [spec for sec in M.SECTIONS for spec in a[sec].values()]
n_assumed = sum(str(spec["source"]).startswith("assumption") for spec in specs)


def reset():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


ui.opening("What could one dialysis centre do?",
           "One haemodialysis centre inside a public hospital. Change the inputs on the left; the results on "
           "the right show how many people it could treat, how much of its capacity it uses, and whether the money "
           "adds up. **Capacity used** = the share of available session slots actually filled. **Payer mix** = "
           "who pays for each session.")
st.html('<div class="note-orange">Example inputs, not data. Defaults come from '
        f'config/assumptions_kidney.yaml; {n_assumed} of {len(specs)} inputs there are assumptions still to verify. '
        'An illustrative model using public data and stated assumptions. Not investment advice.</div>')

left, right = st.columns([1, 1.25], gap="large")
with left:
    with st.container(key="panel_inputs"):
        st.markdown("**The centre**")
        c = st.columns(2)
        c[0].number_input("Machines", 1, 40, key="cm_machines")
        c[1].number_input("Shifts per day", 1, 3, key="cm_shifts")
        c[0].number_input("Days open per week", 1, 7, key="cm_days")
        c[1].number_input("Sessions per patient per week", 1, 3, key="cm_spp")
        st.slider("Capacity used (% of slots filled)", 10, 100, key="cm_used", format="%d%%")
        st.markdown("**The money**")
        st.number_input("Price per session paid out of pocket (₦)", 5_000, 200_000, step=1_000, key="cm_price")
        c = st.columns(3)
        c[0].number_input("Subsidised %", 0, 100, key="cm_sub")
        c[1].number_input("NHIA %", 0, 100, key="cm_nhia")
        c[2].number_input("Employer/HMO %", 0, 100, key="cm_hmo")
        oop = 100 - st.session_state.cm_sub - st.session_state.cm_nhia - st.session_state.cm_hmo
        if oop < 0:
            st.error("The insured and subsidised shares add up to more than 100%. Lower one of them.")
            st.stop()
        st.caption(f"Shares of sessions. Out of pocket: {oop}% (what's left). Prices for subsidised "
                   f"({story.naira(base['price_subsidised_ngn'])}), NHIA ({story.naira(base['price_nhia_ngn'])}) "
                   f"and employer/HMO ({story.naira(base['price_employer_hmo_ngn'])}) sessions stay at the "
                   "base-case assumptions.")
        c = st.columns(2)
        c[0].number_input("Consumables per session (US$, imported)", 1.0, 200.0, step=1.0, key="cm_cons")
        c[1].number_input("Power and water per session (₦)", 0, 50_000, step=500, key="cm_power")
        st.number_input("Staff cost per shift (₦: nurses, technician, share of a nephrologist)", 0, 1_000_000,
                        step=5_000, key="cm_staff")
        st.segmented_control("Naira shock (imported costs)", ["No shock", "+20%", "+50%"], key="cm_shock")
        st.button("Reset to base case", on_click=reset)

ss = st.session_state
x = {**base, "machines": ss.cm_machines, "shifts_per_day": ss.cm_shifts, "days_open_per_week": ss.cm_days,
     "capacity_used": ss.cm_used / 100, "sessions_per_patient_per_week": ss.cm_spp,
     "price_out_of_pocket_ngn": ss.cm_price, "consumables_per_session_usd": ss.cm_cons,
     "power_water_per_session_ngn": ss.cm_power, "staff_cost_per_shift_ngn": ss.cm_staff,
     "payer_mix": {"out_of_pocket": (oop / 100, "price_out_of_pocket_ngn"),
                   "subsidised": (ss.cm_sub / 100, "price_subsidised_ngn"),
                   "nhia": (ss.cm_nhia / 100, "price_nhia_ngn"),
                   "employer_hmo": (ss.cm_hmo / 100, "price_employer_hmo_ngn")}}
shock = {"No shock": 0.0, "+20%": 0.2, "+50%": 0.5}[ss.cm_shock or "No shock"]
r = M.run(x, naira_shock=shock)

with right:
    st.html(
        f'<div class="card measure"><div class="label">Measure</div>'
        f'<div style="display:flex;gap:2.5rem;flex-wrap:wrap">'
        f'<div><div class="big-number" style="color:{cs.ORANGE_TEXT}">{r["patients_treated"]:.0f}</div>'
        f'<div class="small-grey">patients treated (on dialysis all year)</div></div>'
        f'<div><div class="big-number">{r["capacity_used"]:.0%}</div><div class="small-grey">capacity used</div>'
        f'</div></div><div class="progress"><div style="width:{min(100, r["capacity_used"] * 100):.0f}%"></div></div>'
        f'<div class="small-grey">{r["weekly_capacity"]:,.0f} sessions possible per week · '
        f'{r["sessions_per_year"]:,.0f} sessions delivered per year</div></div>')
    st.write("")
    m = 12
    income, costs = r["revenue_per_year_ngn"] / m, (r["variable_cost_per_year_ngn"] + r["fixed_cost_per_year_ngn"]) / m
    result = income - costs
    col = cs.GOOD if result >= 0 else cs.BAD
    st.html(
        f'<div class="card"><div class="label">Per month (running costs, before paying back equipment)</div>'
        f'<div class="bar-row"><div class="name">Income</div><div class="val" style="width:auto">'
        f'{story.naira(income)}</div></div>'
        f'<div class="bar-row"><div class="name">Costs</div><div class="val" style="width:auto">'
        f'{story.naira(costs)}</div></div>'
        f'<div class="bar-row"><div class="name"><b>Result</b></div><div class="val" style="width:auto;color:{col}">'
        f'{story.naira(result)}</div></div>'
        f'<div class="line" style="margin-top:8px">{html.escape(story.breakeven_sentence(r))}</div>'
        f'<div class="small-grey" style="margin-top:6px">Average price received {story.naira(r["average_price_ngn"])} '
        f'a session; break-even price {story.naira(r["breakeven_price_ngn"])}. Exchange rate '
        f'₦{r["fx_ngn_per_usd"]:,.0f} per US$ (World Bank {M.fx_source_year()}'
        f'{f", naira {shock:.0%} weaker" if shock else ""}). Set-up capital '
        f'{story.naira(r["setup_capital_ngn"], short=True)}; payback '
        f'{"never at these inputs" if r["payback_years"] == float("inf") else f"{r["payback_years"]:.1f} years"}.'
        f'</div></div>')
    st.write("")
    with st.container(border=True):
        st.markdown("**Who carries the shortfall? Two PPP structures**")
        st.caption("A PPP (public-private partnership): a private partner pays for equipment, set-up, maintenance "
                   "and consumables; the hospital pays staff, power and water. Illustrative structures, general "
                   "examples only. Not any real firm's terms.")
        choice = st.segmented_control("Structure", ["Fee per session", "Revenue share"], key="cm_ppp")
        structure = "share" if choice == "Revenue share" else "fee"
        p = M.run_ppp(x, structure, naira_shock=shock)
        term = (f"the hospital pays the partner {story.naira(x['partner_fee_per_session_ngn'])} a session"
                if structure == "fee" else f"the partner receives {x['partner_revenue_share']:.0%} of session income")
        c = st.columns(2)
        for colx, who, key in [(c[0], "Private partner", "partner"), (c[1], "Host hospital", "hospital")]:
            v = p[f"{key}_net_cash_ngn"] / m
            colx.html(ui.card(who, story.naira(v, short=True),
                              f'<span style="color:{cs.GOOD if v >= 0 else cs.BAD}">a month, net</span>'))
        st.caption(f"Here {term}. Whichever structure is used, the total shortfall or surplus is the same; the "
                   "structure only decides who carries it.")

ui.footer("Illustrative centre model (config/assumptions_kidney.yaml); prices from the kidney register; "
          "World Bank exchange rate (PA.NUS.FCRF)",
          f"exchange rate {M.fx_source_year()} (annual average)")
