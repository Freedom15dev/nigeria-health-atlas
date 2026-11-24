"""Phase 4 tests: the centre model against one case worked by hand.

HAND-WORKED CASE (round numbers so every step can be checked on paper)

Inputs
  2 machines, 2 shifts a day, open 5 days a week, 50% of slots used, 2 sessions per patient a week
  everyone pays out of pocket at N50,000 a session
  exchange rate N1,000 per US$
  consumables US$10 a session; power and water N5,000 a session
  staff N20,000 per shift; maintenance 10% of equipment cost a year
  equipment US$10,000 per machine; set-up US$5,000; equipment life 5 years

Capacity and patients
  weekly capacity    = 2 x 2 x 5            = 20 session slots
  sessions per week  = 20 x 0.5             = 10
  patients treated   = 10 / 2               = 5
  sessions per year  = 10 x 52              = 520      (slots per year = 20 x 52 = 1,040)

Money
  average price      = 1.0 x 50,000         = N50,000
  variable / session = 10 x 1,000 + 5,000   = N15,000
  equipment          = 2 x 10,000 x 1,000   = N20,000,000
  set-up capital     = 20,000,000 + 5,000 x 1,000 = N25,000,000
  staff / year       = 20,000 x 2 x 5 x 52  = N10,400,000
  maintenance / year = 0.10 x 20,000,000    = N2,000,000
  fixed / year       = 10,400,000 + 2,000,000 = N12,400,000
  revenue / year     = 520 x 50,000         = N26,000,000
  variable / year    = 520 x 15,000         = N7,800,000
  net cash / year    = 26,000,000 - 7,800,000 - 12,400,000 = N5,800,000
  break-even capacity used = 12,400,000 / (50,000 - 15,000) / 1,040 = 354.29 / 1,040 = 0.3407
  break-even price   = (12,400,000 + 7,800,000) / 520 = N38,846.15
  payback            = 25,000,000 / 5,800,000 = 4.31 years
  cost per patient-year = (12,400,000 + 7,800,000 + 25,000,000 / 5) / 5 = N5,040,000

Naira 50% weaker (N1,500 per US$)
  variable / session = 10 x 1,500 + 5,000 = N20,000; equipment N30,000,000; maintenance N3,000,000
  net cash / year    = 26,000,000 - 520 x 20,000 - (10,400,000 + 3,000,000) = N2,200,000

Illustrative PPP, fee of N30,000 a session (partner pays consumables and maintenance)
  partner: income 520 x 30,000 = 15,600,000; costs 520 x 10,000 + 2,000,000 = 7,200,000; net 8,400,000
  hospital: income 26,000,000 - 15,600,000 = 10,400,000; costs 10,400,000 + 520 x 5,000 = 13,000,000; net -2,600,000
"""
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import centre_model as M  # noqa: E402


def hand_case():
    return {
        "machines": 2, "shifts_per_day": 2, "days_open_per_week": 5, "capacity_used": 0.5,
        "sessions_per_patient_per_week": 2,
        "price_out_of_pocket_ngn": 50_000,
        "payer_mix": {"out_of_pocket": (1.0, "price_out_of_pocket_ngn")},
        "fx_ngn_per_usd": 1_000,
        "consumables_per_session_usd": 10, "power_water_per_session_ngn": 5_000,
        "staff_cost_per_shift_ngn": 20_000, "maintenance_pct_of_equipment_per_year": 0.10,
        "equipment_cost_per_machine_usd": 10_000, "setup_cost_usd": 5_000, "equipment_life_years": 5,
        "partner_fee_per_session_ngn": 30_000, "partner_revenue_share": 0.5,
    }


def test_capacity_and_patients_match_hand_calculation():
    r = M.run(hand_case())
    assert r["weekly_capacity"] == 20
    assert r["sessions_per_week"] == 10
    assert r["patients_treated"] == 5
    assert r["sessions_per_year"] == 520


def test_money_matches_hand_calculation():
    r = M.run(hand_case())
    assert r["average_price_ngn"] == 50_000
    assert r["variable_cost_per_session_ngn"] == 15_000
    assert r["setup_capital_ngn"] == 25_000_000
    assert r["fixed_cost_per_year_ngn"] == 12_400_000
    assert r["net_cash_per_year_ngn"] == 5_800_000
    assert r["breakeven_capacity_used"] == pytest.approx(0.3407, abs=1e-4)
    assert r["breakeven_price_ngn"] == pytest.approx(38_846.15, abs=0.01)
    assert r["payback_years"] == pytest.approx(4.31, abs=0.01)
    assert r["cost_per_patient_year_ngn"] == 5_040_000


def test_naira_shock_matches_hand_calculation():
    r = M.run(hand_case(), naira_shock=0.5)
    assert r["fx_ngn_per_usd"] == 1_500
    assert r["variable_cost_per_session_ngn"] == 20_000
    assert r["net_cash_per_year_ngn"] == 2_200_000


def test_ppp_fee_matches_hand_calculation():
    p = M.run_ppp(hand_case(), "fee")
    assert p["partner_net_cash_ngn"] == 8_400_000
    assert p["hospital_net_cash_ngn"] == -2_600_000
    assert p["partner_payback_years"] == pytest.approx(25_000_000 / 8_400_000)


def test_ppp_share_splits_revenue():
    p = M.run_ppp(hand_case(), "share")
    assert p["partner_income_ngn"] == 13_000_000 and p["hospital_income_ngn"] == 13_000_000


def test_loss_making_centre_has_no_payback():
    x = {**hand_case(), "price_out_of_pocket_ngn": 10_000}  # below the N15,000 variable cost
    r = M.run(x)
    assert math.isinf(r["payback_years"]) and math.isinf(r["breakeven_capacity_used"])


def test_payer_mix_must_sum_to_one():
    x = {**hand_case(), "payer_mix": {"out_of_pocket": (0.9, "price_out_of_pocket_ngn")}}
    with pytest.raises(ValueError):
        M.run(x)


def test_assumptions_file_is_complete_and_scenarios_order_correctly():
    a = M.load_assumptions()
    for section in M.SECTIONS:
        for name, spec in a[section].items():
            for key in ("value", "low", "high", "unit", "source", "worse"):
                assert key in spec, f"{section}.{name} missing {key}"
    nets = {sc: M.run(M.scenario_inputs(a, sc))["net_cash_per_year_ngn"] for sc in ("low", "base", "high")}
    assert nets["low"] < nets["base"] < nets["high"]
