"""One illustrative specialist centre: patients treated, capacity used, break-even.
Used for a haemodialysis centre (kidney) and a radiotherapy centre (cancer), with different inputs.

An illustrative model using public data and stated assumptions. Not investment advice.
Every input comes from config/assumptions_<specialty>.yaml. Nothing is hard-coded here.

Capacity and patients
  weekly_capacity     = machines x shifts_per_day x sessions_per_machine_per_shift x days_open_per_week
                        (session slots; sessions_per_machine_per_shift is 1 for dialysis, many for a linac)
  sessions_delivered  = weekly_capacity x capacity_used                       (per week)
  yearly figures      = weekly x 52
  patients_treated:
    patient_basis "ongoing" (dialysis)  = sessions per week / sessions_per_patient_per_week
                                          (people on treatment all year)
    patient_basis "course" (radiotherapy) = sessions per year / sessions_per_course
                                          (patients completing a course in a year)
  price_basis "course": prices are per course; price per session = price / sessions_per_course

Money (NGN, per year)
  average price       = sum over payers of (share x price)
  variable cost       = per session: consumables (US$ x exchange rate) + power and water
  fixed cost          = staff (per shift x shifts x days x 52) + maintenance (% of equipment cost)
  set-up capital      = machines x equipment cost (US$) + set-up cost (US$), at the exchange rate
  depreciation        = set-up capital / equipment life
  net cash            = revenue - variable cost - fixed cost        (before depreciation)
  break-even capacity used = fixed cost / (price - variable cost per session) / yearly session slots
  break-even price    = (fixed cost + variable cost) / sessions delivered
  payback (years)     = set-up capital / net cash
  cost per patient-year = (fixed + variable + depreciation) / patients treated
                        (for "course", this is the cost per patient treated in the year)
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
ASSUMPTIONS = ROOT / "config" / "assumptions_kidney.yaml"
ASSUMPTIONS_CANCER = ROOT / "config" / "assumptions_cancer.yaml"
WDI = ROOT / "data" / "processed" / "wdi_nga.csv"
SECTIONS = ["capacity", "prices", "costs", "fx", "ppp"]
WEEKS = 52


# ---------- inputs ----------

def load_assumptions(path: Path = ASSUMPTIONS) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve(v):
    """'from_data:wdi:<indicator>' -> latest yearly value from the processed WDI file."""
    if isinstance(v, str) and v.startswith("from_data:wdi:"):
        ind = v.split(":", 2)[2]
        w = pd.read_csv(WDI)
        w = w[w.indicator_id == ind].sort_values("year")
        if w.empty:
            raise ValueError(f"{ind} not in {WDI}")
        return float(w.value.iloc[-1])
    return v


def fx_source_year(path: Path = WDI) -> int:
    w = pd.read_csv(path)
    return int(w[w.indicator_id == "PA.NUS.FCRF"].year.max())


def scenario_inputs(a: dict, scenario: str = "base") -> dict:
    """Flat dict of inputs for one scenario.
    base: every input at its value. low: each input at its pessimistic ('worse') bound.
    high: each input at its optimistic bound. Design inputs ('worse: fixed') keep their value."""
    out = {}
    for section in SECTIONS:
        for name, spec in a[section].items():
            if scenario == "base" or spec["worse"] == "fixed":
                col = "value"
            elif scenario == "low":
                col = spec["worse"]
            elif scenario == "high":
                col = "high" if spec["worse"] == "low" else "low"
            else:
                raise ValueError(f"unknown scenario {scenario}")
            out[name] = _resolve(spec[col])
    out["payer_mix"] = {p: (v["value"], v["price"]) for p, v in a["payer_mix"].items() if isinstance(v, dict)}
    out["patient_basis"] = a.get("patient_basis", "ongoing")
    out["price_basis"] = a.get("price_basis", "session")
    return out


def payer_mix_column(a: dict, column: str) -> dict:
    """The payer mix for 'value', 'low' (mostly out-of-pocket) or 'high' (more insured)."""
    return {p: (v[column], v["price"]) for p, v in a["payer_mix"].items() if isinstance(v, dict)}


# ---------- the model ----------

def run(x: dict, naira_shock: float = 0.0) -> dict:
    """Run the model for one set of inputs. naira_shock = 0.2 means the naira is 20% weaker
    (20% more NGN per US$); naira prices stay the same, imported costs rise."""
    shares = [s for s, _ in x["payer_mix"].values()]
    if abs(sum(shares) - 1) > 1e-9:
        raise ValueError(f"payer mix sums to {sum(shares)}, not 1")
    fx = x["fx_ngn_per_usd"] * (1 + naira_shock)

    per_shift = x.get("sessions_per_machine_per_shift", 1)
    weekly_capacity = x["machines"] * x["shifts_per_day"] * per_shift * x["days_open_per_week"]
    sessions_week = weekly_capacity * x["capacity_used"]
    sessions_year = sessions_week * WEEKS
    slots_year = weekly_capacity * WEEKS
    course = x.get("patient_basis", "ongoing") == "course"
    if course:
        patients = sessions_year / x["sessions_per_course"]
    else:
        patients = sessions_week / x["sessions_per_patient_per_week"]

    avg_price = sum(share * x[price] for share, price in x["payer_mix"].values())
    if x.get("price_basis", "session") == "course":
        avg_price = avg_price / x["sessions_per_course"]   # price per course -> price per session
    variable_per_session = x["consumables_per_session_usd"] * fx + x["power_water_per_session_ngn"]
    equipment_ngn = x["machines"] * x["equipment_cost_per_machine_usd"] * fx
    capex = equipment_ngn + x["setup_cost_usd"] * fx
    staff_year = x["staff_cost_per_shift_ngn"] * x["shifts_per_day"] * x["days_open_per_week"] * WEEKS
    maintenance_year = x["maintenance_pct_of_equipment_per_year"] * equipment_ngn
    fixed_year = staff_year + maintenance_year
    depreciation_year = capex / x["equipment_life_years"]

    revenue_year = sessions_year * avg_price
    variable_year = sessions_year * variable_per_session
    net_cash_year = revenue_year - variable_year - fixed_year
    contribution = avg_price - variable_per_session

    be_sessions = fixed_year / contribution if contribution > 0 else math.inf
    be_price = (fixed_year + variable_year) / sessions_year
    return {
        "patient_basis": "course" if course else "ongoing",
        "naira_shock": naira_shock,
        "fx_ngn_per_usd": fx,
        "weekly_capacity": weekly_capacity,
        "sessions_per_week": sessions_week,
        "sessions_per_year": sessions_year,
        "patients_treated": patients,
        "capacity_used": x["capacity_used"],
        "average_price_ngn": avg_price,
        "variable_cost_per_session_ngn": variable_per_session,
        "revenue_per_year_ngn": revenue_year,
        "variable_cost_per_year_ngn": variable_year,
        "fixed_cost_per_year_ngn": fixed_year,
        "depreciation_per_year_ngn": depreciation_year,
        "net_cash_per_year_ngn": net_cash_year,
        "setup_capital_ngn": capex,
        "breakeven_capacity_used": be_sessions / slots_year if contribution > 0 else math.inf,
        "breakeven_price_ngn": be_price,
        "breakeven_price_per_course_ngn": be_price * x["sessions_per_course"] if course else math.nan,
        "average_price_per_course_ngn": avg_price * x["sessions_per_course"] if course else math.nan,
        "payback_years": capex / net_cash_year if net_cash_year > 0 else math.inf,
        "cost_per_patient_year_ngn": (fixed_year + variable_year + depreciation_year) / patients,
    }


def run_ppp(x: dict, structure: str, naira_shock: float = 0.0) -> dict:
    """Split one centre's money between a private partner and the host hospital.
    ILLUSTRATIVE structures, general examples only:
      'fee'   - the hospital pays the partner a fixed fee per session
      'share' - the partner receives a share of session revenue
    Cost split (from the assumptions): partner pays equipment, set-up, maintenance, consumables;
    hospital pays staff, power and water."""
    r = run(x, naira_shock)
    fx = r["fx_ngn_per_usd"]
    s = r["sessions_per_year"]
    if structure == "fee":
        partner_income = x["partner_fee_per_session_ngn"] * s
    elif structure == "share":
        partner_income = x["partner_revenue_share"] * r["revenue_per_year_ngn"]
    else:
        raise ValueError("structure must be 'fee' or 'share'")
    equipment_ngn = x["machines"] * x["equipment_cost_per_machine_usd"] * fx
    partner_costs = (x["consumables_per_session_usd"] * fx * s
                     + x["maintenance_pct_of_equipment_per_year"] * equipment_ngn)
    hospital_income = r["revenue_per_year_ngn"] - partner_income
    hospital_costs = (r["fixed_cost_per_year_ngn"] - x["maintenance_pct_of_equipment_per_year"] * equipment_ngn
                      + x["power_water_per_session_ngn"] * s)
    partner_net = partner_income - partner_costs
    return {
        "structure": structure,
        "partner_income_ngn": partner_income,
        "partner_costs_ngn": partner_costs,
        "partner_net_cash_ngn": partner_net,
        "partner_payback_years": r["setup_capital_ngn"] / partner_net if partner_net > 0 else math.inf,
        "hospital_income_ngn": hospital_income,
        "hospital_costs_ngn": hospital_costs,
        "hospital_net_cash_ngn": hospital_income - hospital_costs,
    }


def input_specs(a: dict):
    """(section, name, spec) for every model input in an assumptions file."""
    for section in SECTIONS:
        for name, spec in a[section].items():
            yield section, name, spec


def run_scenarios(a: dict | None = None) -> pd.DataFrame:
    """Low / base / high, each at today's exchange rate and under each naira shock."""
    a = a or load_assumptions()
    shocks = [0.0, *a["fx"]["naira_shocks"]["value"]]
    rows = []
    for sc in ("low", "base", "high"):
        x = scenario_inputs(a, sc)
        for shock in shocks:
            rows.append({"scenario": sc, **run(x, shock)})
    return pd.DataFrame(rows)


def run_ppp_table(a: dict | None = None) -> pd.DataFrame:
    a = a or load_assumptions()
    x = scenario_inputs(a, "base")
    shocks = [0.0, *a["fx"]["naira_shocks"]["value"]]
    return pd.DataFrame([{"naira_shock": s, **run_ppp(x, st, s)} for st in ("fee", "share") for s in shocks])
