"""Phase 4: run the illustrative dialysis centre model and save the results.

Writes:
  data/processed/centre_model_scenarios.csv   low / base / high x naira shocks
  data/processed/centre_model_ppp.csv         illustrative PPP splits (fee, revenue share)
  data/processed/centre_model_sensitivity.csv one-at-a-time swing of each input (low and high)
  exports/centre_model_scenarios.csv          the same scenario table for the analyst pack
  ... and the same four files with a cancer_ prefix (radiotherapy centre), once
  config/assumptions_cancer.yaml exists
An illustrative model using public data and stated assumptions. Not investment advice.
"""
import sys

import pandas as pd

from common import EXPORTS, PROCESSED, ROOT

sys.path.insert(0, str(ROOT / "src"))
import centre_model as M  # noqa: E402


def sensitivity(a: dict) -> pd.DataFrame:
    """Move one input at a time to its low and high bound (everything else at base) and record
    the change in yearly net cash. Shows which assumptions matter most."""
    base_x = M.scenario_inputs(a, "base")
    base = M.run(base_x)["net_cash_per_year_ngn"]
    rows = []
    for section in M.SECTIONS:
        for name, spec in a[section].items():
            if spec["worse"] == "fixed" or not isinstance(spec["value"], (int, float)) or isinstance(spec["value"], bool):
                continue
            out = {"input": name, "section": section, "unit": spec["unit"], "source": spec["source"],
                   "base_value": spec["value"]}
            for bound in ("low", "high"):
                r = M.run({**base_x, name: spec[bound]})
                out[f"{bound}_value"] = spec[bound]
                out[f"net_cash_at_{bound}_ngn"] = r["net_cash_per_year_ngn"]
            out["swing_ngn"] = abs(out["net_cash_at_high_ngn"] - out["net_cash_at_low_ngn"])
            out["base_net_cash_ngn"] = base
            out["verified"] = not spec["source"].startswith("assumption")
            rows.append(out)
    return pd.DataFrame(rows).sort_values("swing_ngn", ascending=False)


PPP_LABEL = "Illustrative structures, general examples only. Not any real firm's terms."


def run_one(a: dict, prefix: str) -> None:
    """Scenarios, PPP splits and sensitivity for one assumptions file. prefix: '' (kidney) or 'cancer_'."""
    sc = M.run_scenarios(a).assign(label=a["label"], fx_year=M.fx_source_year())
    sc.to_csv(PROCESSED / f"centre_model_{prefix}scenarios.csv", index=False)
    EXPORTS.mkdir(exist_ok=True)
    sc.to_csv(EXPORTS / f"centre_model_{prefix}scenarios.csv", index=False)
    M.run_ppp_table(a).assign(label=PPP_LABEL).to_csv(PROCESSED / f"centre_model_{prefix}ppp.csv", index=False)
    sens = sensitivity(a)
    sens.to_csv(PROCESSED / f"centre_model_{prefix}sensitivity.csv", index=False)
    b = sc[(sc.scenario == "base") & (sc.naira_shock == 0)].iloc[0]
    unit = "courses a year" if b.patient_basis == "course" else "patients on treatment"
    print(f"  {prefix or 'kidney_'}base case: {b.patients_treated:.0f} {unit}, {b.sessions_per_year:,.0f} "
          f"sessions; price received N{b.average_price_ngn:,.0f} vs break-even N{b.breakeven_price_ngn:,.0f} a session")
    print(f"  biggest driver of net cash: {sens.iloc[0]['input']} (verified source: {sens.iloc[0]['verified']})")


def main() -> None:
    run_one(M.load_assumptions(), "")
    if M.ASSUMPTIONS_CANCER.exists():
        run_one(M.load_assumptions(M.ASSUMPTIONS_CANCER), "cancer_")

if __name__ == "__main__":
    main()
