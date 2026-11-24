"""Phase 2: build the state scorecard and the weight stress-test.

Writes:
  data/processed/scorecard.csv          37 rows, pillar scores, total, rank
  data/processed/scorecard_stress.csv   share of weightings that keep each state in the top 10
  exports/scorecard_top5_bottom5.csv    both ends of the ranking, pillars visible
A screening tool, not investment advice.
"""
import sys

import pandas as pd

from common import EXPORTS, PROCESSED, ROOT

sys.path.insert(0, str(ROOT / "src"))
from scoring import LABEL, PILLARS_NEED_POP_ONLY, TOP_N, build_scorecard, stress_test, weight_grid  # noqa: E402


def main() -> None:
    panel = pd.read_csv(PROCESSED / "state_panel.csv")
    sc = build_scorecard(panel)
    sc.to_csv(PROCESSED / "scorecard.csv", index=False)
    st = stress_test(panel)
    st.to_csv(PROCESSED / "scorecard_stress.csv", index=False)

    # Sensitivity: Need from population alone (no self-reported diagnosis inputs).
    alt = build_scorecard(panel, pillars=PILLARS_NEED_POP_ONLY)
    sens = sc[["state", "rank"]].merge(alt[["state", "rank", "score_total"]].rename(
        columns={"rank": "rank_need_pop_only", "score_total": "score_total_need_pop_only"}), on="state")
    sens["rank_change"] = sens["rank"] - sens["rank_need_pop_only"]
    sens["label"] = LABEL
    sens.to_csv(PROCESSED / "scorecard_sensitivity_need.csv", index=False)

    cols = ["rank", "state", "score_need", "score_supply_gap", "score_ability_to_pay", "score_total"]
    ends = pd.concat([sc.head(5).assign(end="top 5"), sc.tail(5).assign(end="bottom 5")])
    EXPORTS.mkdir(exist_ok=True)
    ends[["end", *cols, "label"]].to_csv(EXPORTS / "scorecard_top5_bottom5.csv", index=False)

    print(f"  {LABEL}")
    print("  Top 5 (equal weights):")
    print(sc.head(5)[cols].to_string(index=False))
    print("  Bottom 5:")
    print(sc.tail(5)[cols].to_string(index=False))
    share = f"share_in_top{TOP_N}_pct"
    robust = st[st[share] >= 80]
    overlap = len(set(sc.head(10).state) & set(alt.nsmallest(10, "rank").state))
    print(f"  Sensitivity (Need = population only): {overlap} of the top 10 unchanged; biggest movers: "
          f"{sens.reindex(sens.rank_change.abs().sort_values(ascending=False).index).head(3)[['state', 'rank', 'rank_need_pop_only']].values.tolist()}")
    print(f"  Stress-test: {len(weight_grid())} weightings; {len(robust)} states stay in the top {TOP_N} "
          f"in at least 80% of them: {robust.state.tolist()}")


if __name__ == "__main__":
    main()
