"""Phase 2 tests: percentile ranks, pillar direction, weights grid, stress-test."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import scoring as S  # noqa: E402


def toy_panel(n=5):
    """Five made-up states. State E has the most people, fewest hospitals and most insurance."""
    i = np.arange(n)
    return pd.DataFrame({
        "state": list("ABCDE")[:n], "state_code": list("abcde")[:n], "zone": "z",
        "population_total": 1_000_000 * (i + 1),
        "bp_ever_told_high_women_pct": 5.0 + i, "bp_ever_told_high_men_pct": 5.0 + i,
        "sugar_ever_told_high_women_pct": 1.0 + i, "sugar_ever_told_high_men_pct": 1.0 + i,
        "fac_sec_tert_per_100k": 5.0 - i,
        "insurance_any_women_pct": 2.0 + i, "insurance_any_men_pct": 2.0 + i,
        "wealth_top2_pct": 10.0 + 10 * i,
    })


def test_percentile_rank_runs_0_to_100():
    r = S.percentile_rank(pd.Series([3, 1, 2, 10], name="x"))
    assert r.min() == 0 and r.max() == 100 and list(r) == pytest.approx([200 / 3, 0, 100 / 3, 100])


def test_percentile_rank_is_unmoved_by_an_outlier():
    a = S.percentile_rank(pd.Series([1, 2, 3, 4], name="x"))
    b = S.percentile_rank(pd.Series([1, 2, 3, 4000], name="x"))
    assert list(a) == list(b)


def test_percentile_rank_refuses_missing():
    with pytest.raises(ValueError):
        S.percentile_rank(pd.Series([1, None, 3], name="x"))


def test_fewer_hospitals_means_bigger_supply_gap():
    sc = S.pillar_scores(toy_panel())
    # E has the fewest hospitals per 100k, so the highest supply-gap score
    assert sc.set_index("state").score_supply_gap.idxmax() == "E"
    assert sc.set_index("state").score_supply_gap.idxmin() == "A"


def test_hand_worked_total():
    """Toy case worked by hand: every input rises from A to E (hospitals fall), so every pillar
    ranks A=0, B=25, C=50, D=75, E=100, and with equal weights the total equals the same."""
    sc = S.build_scorecard(toy_panel()).set_index("state")
    assert sc.loc["E", "score_total"] == 100 and sc.loc["A", "score_total"] == 0
    assert sc.loc["C", "score_total"] == 50
    assert sc.loc["E", "rank"] == 1 and (sc.label == S.LABEL).all()


def test_weight_grid_rules():
    grid = S.weight_grid()
    assert all(abs(sum(w.values()) - 1) < 1e-9 for w in grid)
    # equal weights are in the grid
    assert any(all(abs(v - 1 / 3) < 1e-9 for v in w.values()) for w in grid)
    # duplicates after normalising are removed: 7^3 = 343 raw combinations
    assert len(grid) < 343 and len({tuple(round(v, 6) for v in w.values()) for w in grid}) == len(grid)
    # every weight lies within the normalised range of the 0.2-0.5 grid
    assert all(0.2 / 1.2 - 1e-9 <= v <= 0.5 / 0.9 + 1e-9 for w in grid for v in w.values())


def test_stress_test_top_state_is_robust_in_toy_case():
    st = S.stress_test(toy_panel(), top_n=1).set_index("state")
    assert st.loc["E", "share_in_top1_pct"] == 100


def test_need_pop_only_variant_changes_only_need():
    a = S.pillar_scores(toy_panel(), S.PILLARS)
    b = S.pillar_scores(toy_panel(), S.PILLARS_NEED_POP_ONLY)
    assert (a.score_supply_gap == b.score_supply_gap).all()
    assert (a.score_ability_to_pay == b.score_ability_to_pay).all()
