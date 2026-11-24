"""Save the analyst-pack charts as PNGs (1600 px wide) to exports/.

Needs kaleido (and a Chrome/Chromium it can find). If image export isn't available,
it warns and carries on: the data outputs don't depend on the PNGs.
"""
import sys

import pandas as pd

from common import EXPORTS, MANUAL, PROCESSED, ROOT

sys.path.insert(0, str(ROOT / "src"))
import charts  # noqa: E402

WIDTH = 1600


def main() -> None:
    panel = pd.read_csv(PROCESSED / "state_panel.csv")
    sc = pd.read_csv(PROCESSED / "scorecard.csv")
    st = pd.read_csv(PROCESSED / "scorecard_stress.csv")
    figs = {
        "chart1_facilities_per_100k": charts.facilities_per_100k(panel),
        "chart2_need_vs_ability_to_pay": charts.need_vs_pay(sc),
        "chart2b_supply_gap_vs_ability_to_pay": charts.gap_vs_pay(sc),
        "chart3_scorecard_top5_bottom5": charts.scorecard_ends(sc),
        "chart3b_scorecard_stress_test": charts.stress_chart(st),
    }
    reg = PROCESSED / "register_kidney_by_state.csv"
    if reg.exists():
        by_state = pd.read_csv(reg)
        national = pd.read_csv(PROCESSED / "register_kidney_national.csv", dtype=str, keep_default_na=False)
        figs["chart4_register_gap_types"] = charts.register_gap_types(by_state)
        figs["chart4b_register_machines_per_million"] = charts.register_machines_per_million(by_state, panel)
        figs["chart4c_national_counts_disagree"] = charts.national_counts(national)
    hf = MANUAL / "headline_figures.csv"
    if hf.exists():
        figs["chart5_out_of_pocket_figures"] = charts.oop_figures(
            pd.read_csv(hf, dtype=str, keep_default_na=False), pd.read_csv(PROCESSED / "wdi_nga.csv"))
    model = PROCESSED / "centre_model_scenarios.csv"
    if model.exists():
        figs["chart6_centre_model_scenarios"] = charts.centre_scenarios(pd.read_csv(model))
        figs["chart6b_centre_model_sensitivity"] = charts.centre_sensitivity(
            pd.read_csv(PROCESSED / "centre_model_sensitivity.csv"))
    EXPORTS.mkdir(exist_ok=True)
    for name, fig in figs.items():
        try:
            # scale keeps text readable at 1600 px: layout is drawn at 1000 px then scaled up
            fig.write_image(EXPORTS / f"{name}.png", width=1000, scale=WIDTH / 1000)
        except Exception as e:  # kaleido/Chrome missing
            print(f"  WARNING: could not export {name}.png ({type(e).__name__}: {e})")
            return
    print(f"  saved {len(figs)} PNGs ({WIDTH} px wide) to exports/")


if __name__ == "__main__":
    main()
