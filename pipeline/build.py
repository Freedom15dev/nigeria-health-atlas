"""Write data/processed/meta.json (data-as-of dates, row counts, checksums, flags)
and print the GRID3 vs eHealth Africa comparison, state by state.
The comparison is also saved to exports/ for the analyst pack.
"""
import json

import pandas as pd

from common import EXPORTS, PROCESSED, RAW_FILES, load_sources, sha256, today
from join_states import CROSSCHECK_THRESHOLD_PCT


def crosscheck(panel: pd.DataFrame) -> pd.DataFrame:
    cc = panel[["state", "fac_all_grid3", "fac_all_eha", "crosscheck_diff_percent", "crosscheck_flag",
                "fac_sec_tert_grid3", "fac_sec_tert_eha", "crosscheck_sec_tert_diff_percent",
                "crosscheck_sec_tert_flag"]].sort_values("crosscheck_diff_percent")
    EXPORTS.mkdir(exist_ok=True)
    cc.to_csv(EXPORTS / "facility_crosscheck_grid3_vs_ehealthafrica.csv", index=False)
    print("\n  GRID3 v2.0 vs eHealth Africa, facilities by state (all levels)")
    print(cc.to_string(index=False))
    print(f"  {int(cc.crosscheck_flag.sum())} of {len(cc)} states differ by more than "
          f"{CROSSCHECK_THRESHOLD_PCT}% (all levels); {int(cc.crosscheck_sec_tert_flag.sum())} of {len(cc)} "
          "differ by more than that for secondary + tertiary.\n"
          "  Note: 81% of GRID3 v2.0 coordinates come from eHealth Africa, so the two are not independent.")
    return cc


def main(steps: dict | None = None) -> None:
    panel = pd.read_csv(PROCESSED / "state_panel.csv")
    cc = crosscheck(panel)
    src = load_sources()
    pop = panel.set_index("state").population_total
    meta = {
        "built": today(),
        "data_as_of": {k: v.get("data_as_of") for k, v in src.items()},
        "raw_files": {k: {"file": p.name, "sha256": sha256(p)} for k, p in RAW_FILES.items() if p.exists()},
        "rows": {"state_panel": len(panel)},
        "pipeline_steps": steps or {},
        "flags": {
            "crosscheck_states_over_20pct": cc.loc[cc.crosscheck_flag, "state"].tolist(),
            "crosscheck_sec_tert_states_over_20pct": cc.loc[cc.crosscheck_sec_tert_flag, "state"].tolist(),
            "population_40plus": "unknown: source file has totals only",
            "population_ogun_above_lagos": bool(pop["Ogun"] > pop["Lagos"]),
            "ndhs_bp_sugar": "self-reported diagnosis, ages 15-49; partly measures access to testing",
            "ndhs_state_confidence_intervals": "not available from API; FR395 Appendix B has state "
                                               "sampling errors only for a few indicators, not insurance or wealth",
        },
    }
    with open(PROCESSED / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)
    print("  wrote meta.json")


if __name__ == "__main__":
    main()
