"""Page 5: Centre model. One illustrative specialist centre (dialysis or radiotherapy): patients treated,
capacity used, break-even. All maths is in src/centre_model.py; this page only collects inputs and shows results."""
import math

import streamlit as st

import centre_model as M
import chart_style as cs
import components as ui
import story

ui.setup()
kind = st.segmented_control("Centre", ["Dialysis centre", "Radiotherapy centre"], default="Dialysis centre",
                            key="cm_kind", label_visibility="collapsed") or "Dialysis centre"
cancer = kind == "Radiotherapy centre"
spec = "cancer" if cancer else "kidney"
a = ui.assumptions(spec)
base = M.scenario_inputs(a, "base")
course = base["patient_basis"] == "course"
per_course = base["price_basis"] == "course"
P = f"cm_{spec}_"   # session-state prefix, so each centre keeps its own inputs
mix0 = {p: v["value"] for p, v in a["payer_mix"].items() if isinstance(v, dict)}
DEFAULTS = {
    "machines": int(base["machines"]), "shifts": int(base["shifts_per_day"]),
    "days": int(base["days_open_per_week"]), "used": int(round(base["capacity_used"] * 100)),
    "price": int(base["price_out_of_pocket_ngn"]),
    "sub": int(round(mix0["subsidised"] * 100)), "nhia": int(round(mix0["nhia"] * 100)),
    "hmo": int(round(mix0["employer_hmo"] * 100)), "cons": float(base["consumables_per_session_usd"]),
    "power": int(base["power_water_per_session_ngn"]), "staff": int(base["staff_cost_per_shift_ngn"]),
    "shock": "No shock", "ppp": "Fee per session",
}
if course:
    DEFAULTS |= {"per_shift": int(base["sessions_per_machine_per_shift"]), "course": int(base["sessions_per_course"])}
else:
    DEFAULTS |= {"spp": int(base["sessions_per_patient_per_week"])}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(P + k, v)
specs = [s for _, _, s in M.input_specs(a)]
n_assumed = sum(str(s["source"]).startswith("assumption") for s in specs)


def reset():
    for k, v in DEFAULTS.items():
        st.session_state[P + k] = v


ss = st.session_state
words = {  # plain words that change with the centre type
    "machine": "Linacs (radiotherapy machines)" if cancer else "Machines",
    "session": "fraction" if cancer else "session",
}
if cancer:
    ui.opening("What could one radiotherapy centre do?",
               "One radiotherapy centre with a **linac** (linear accelerator, the machine that delivers radiation "
               "treatment). A patient has a **course** of many daily treatments, called **fractions**, over a few "
               "weeks. Change the inputs on the left; the results show how many patients it could treat in a year, "
               "how much of its capacity it uses, and whether the money adds up.")
else:
    ui.opening("What could one dialysis centre do?",
               "One haemodialysis centre inside a public hospital. Change the inputs on the left; the results on "
               "the right show how many people it could treat, how much of its capacity it uses, and whether the "
               "money adds up. **Capacity used** = the share of available session slots actually filled. "
               "**Payer mix** = who pays for each session.")
st.html(f'<div class="note-orange">Example inputs, not data. Defaults come from config/assumptions_{spec}.yaml; '
        f'{n_assumed} of {len(specs)} inputs there are assumptions still to verify. {a["label"]}</div>')

left, right = st.columns([1, 1.25], gap="large")
with left:
    with st.container(key="panel_inputs"):
        st.markdown("**The centre**")
        c = st.columns(2)
        c[0].number_input(words["machine"], 1, 40, key=P + "machines")
        c[1].number_input("Shifts per day", 1, 3, key=P + "shifts")
        c[0].number_input("Days open per week", 1, 7, key=P + "days")
        if course:
            c[1].number_input("Fractions per machine per shift", 1, 80, key=P + "per_shift")
            st.number_input("Fractions per course", 1, 45, key=P + "course")
        else:
            c[1].number_input("Sessions per patient per week", 1, 3, key=P + "spp")
        st.slider("Capacity used (% of slots filled)", 10, 100, key=P + "used", format="%d%%")
        st.markdown("**The money**")
        st.number_input(f"Price paid out of pocket, per {'course' if per_course else 'session'} (₦)", 1_000,
                        50_000_000, step=50_000 if per_course else 1_000, key=P + "price")
        c = st.columns(3)
        c[0].number_input("Subsidised %", 0, 100, key=P + "sub")
        c[1].number_input("NHIA %", 0, 100, key=P + "nhia")
        c[2].number_input("Employer/HMO %", 0, 100, key=P + "hmo")
        oop = 100 - ss[P + "sub"] - ss[P + "nhia"] - ss[P + "hmo"]
        if oop < 0:
            st.error("The insured and subsidised shares add up to more than 100%. Lower one of them.")
            st.stop()
        unit_word = "course" if per_course else "session"
        st.caption(f"Shares of {'patients' if per_course else 'sessions'}. Out of pocket: {oop}% (what's left). "
                   f"Prices per {unit_word} for subsidised ({story.naira(base['price_subsidised_ngn'])}), NHIA "
                   f"({story.naira(base['price_nhia_ngn'])}) and employer/HMO "
                   f"({story.naira(base['price_employer_hmo_ngn'])}) stay at the base-case assumptions.")
        c = st.columns(2)
        c[0].number_input(f"Consumables per {words['session']} (US$, imported)", 0.0, 500.0, step=1.0,
                          key=P + "cons")
        c[1].number_input(f"Power and water per {words['session']} (₦)", 0, 100_000, step=500, key=P + "power")
        st.number_input("Staff cost per shift (₦)", 0, 5_000_000, step=5_000, key=P + "staff",
                        help=a["costs"]["staff_cost_per_shift_ngn"]["unit"])
        st.segmented_control("Naira shock (imported costs)", ["No shock", "+20%", "+50%"], key=P + "shock")
        st.button("Reset to base case", on_click=reset)

x = {**base, "machines": ss[P + "machines"], "shifts_per_day": ss[P + "shifts"],
     "days_open_per_week": ss[P + "days"], "capacity_used": ss[P + "used"] / 100,
     "price_out_of_pocket_ngn": ss[P + "price"], "consumables_per_session_usd": ss[P + "cons"],
     "power_water_per_session_ngn": ss[P + "power"], "staff_cost_per_shift_ngn": ss[P + "staff"],
     "payer_mix": {"out_of_pocket": (oop / 100, "price_out_of_pocket_ngn"),
                   "subsidised": (ss[P + "sub"] / 100, "price_subsidised_ngn"),
                   "nhia": (ss[P + "nhia"] / 100, "price_nhia_ngn"),
                   "employer_hmo": (ss[P + "hmo"] / 100, "price_employer_hmo_ngn")}}
if course:
    x |= {"sessions_per_machine_per_shift": ss[P + "per_shift"], "sessions_per_course": ss[P + "course"]}
else:
    x |= {"sessions_per_patient_per_week": ss[P + "spp"]}
shock = {"No shock": 0.0, "+20%": 0.2, "+50%": 0.5}[ss[P + "shock"] or "No shock"]
r = M.run(x, naira_shock=shock)

with right:
    who = "patients treated in a year (courses completed)" if course else "patients treated (on dialysis all year)"
    st.html(
        f'<div class="card measure"><div class="label">Measure</div>'
        f'<div style="display:flex;gap:2.5rem;flex-wrap:wrap">'
        f'<div><div class="big-number" style="color:{cs.ORANGE_TEXT}">{r["patients_treated"]:,.0f}</div>'
        f'<div class="small-grey">{who}</div></div>'
        f'<div><div class="big-number">{r["capacity_used"]:.0%}</div><div class="small-grey">capacity used</div>'
        f'</div></div><div class="progress"><div style="width:{min(100, r["capacity_used"] * 100):.0f}%"></div></div>'
        f'<div class="small-grey">{r["weekly_capacity"]:,.0f} {words["session"]}s possible per week · '
        f'{r["sessions_per_year"]:,.0f} {words["session"]}s delivered per year</div></div>')
    st.write("")
    m = 12
    income, costs = r["revenue_per_year_ngn"] / m, (r["variable_cost_per_year_ngn"] + r["fixed_cost_per_year_ngn"]) / m
    result = income - costs
    col = cs.GOOD if result >= 0 else cs.BAD
    if course:
        price_line = (f"Average price received {story.naira(r['average_price_per_course_ngn'])} a course; break-even "
                      f"{story.naira(r['breakeven_price_per_course_ngn'])} a course.")
    else:
        price_line = (f"Average price received {story.naira(r['average_price_ngn'])} a session; break-even price "
                      f"{story.naira(r['breakeven_price_ngn'])}.")
    payback = "never at these inputs" if not math.isfinite(r["payback_years"]) else f"{r['payback_years']:.1f} years"
    st.html(
        f'<div class="card"><div class="label">Per month (running costs, before paying back equipment)</div>'
        f'<div class="bar-row"><div class="name">Income</div><div class="val" style="width:auto">'
        f'{story.naira(income)}</div></div>'
        f'<div class="bar-row"><div class="name">Costs</div><div class="val" style="width:auto">'
        f'{story.naira(costs)}</div></div>'
        f'<div class="bar-row"><div class="name"><b>Result</b></div><div class="val" style="width:auto;color:{col}">'
        f'{story.naira(result)}</div></div>'
        f'<div class="line" style="margin-top:8px">{story.breakeven_sentence(r)}</div>'
        f'<div class="small-grey" style="margin-top:6px">{price_line} Exchange rate '
        f'₦{r["fx_ngn_per_usd"]:,.0f} per US$ (World Bank {M.fx_source_year()}'
        f'{f", naira {shock:.0%} weaker" if shock else ""}). Set-up capital '
        f'{story.naira(r["setup_capital_ngn"], short=True)}; payback {payback}.</div></div>')
    st.write("")
    with st.container(border=True):
        st.markdown("**Who carries the shortfall? Two PPP structures**")
        st.caption("A PPP (public-private partnership): a private partner pays for equipment, set-up, maintenance "
                   "and consumables; the hospital pays staff, power and water. Illustrative structures, general "
                   "examples only. Not any real firm's terms.")
        choice = st.segmented_control("Structure", ["Fee per session", "Revenue share"], key=P + "ppp")
        structure = "share" if choice == "Revenue share" else "fee"
        p = M.run_ppp(x, structure, naira_shock=shock)
        term = (f"the hospital pays the partner {story.naira(x['partner_fee_per_session_ngn'])} a {words['session']}"
                if structure == "fee" else f"the partner receives {x['partner_revenue_share']:.0%} of income")
        c = st.columns(2)
        for colx, name, key in [(c[0], "Private partner", "partner"), (c[1], "Host hospital", "hospital")]:
            v = p[f"{key}_net_cash_ngn"] / m
            colx.html(ui.card(name, story.naira(v, short=True),
                              f'<span style="color:{cs.GOOD if v >= 0 else cs.BAD}">a month, net</span>'))
        st.caption(f"Here {term}. Whichever structure is used, the total shortfall or surplus is the same; the "
                   "structure only decides who carries it.")

ui.footer(f"Illustrative centre model (config/assumptions_{spec}.yaml); prices from the {spec} register; "
          "World Bank exchange rate (PA.NUS.FCRF)", f"exchange rate {M.fx_source_year()} (annual average)")
