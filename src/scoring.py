"""State scorecard: three pillars, equal weights, percentile ranks.

A screening tool, not investment advice.

How a score is built, in plain words:
1. Each input (e.g. insurance coverage) is turned into a percentile rank from 0 to 100:
   0 = lowest of the 37 states, 100 = highest. Ranks are used instead of raw values so
   one extreme state (like Lagos on wealth) can't squash everyone else into a narrow band.
2. For inputs where "less" means "more of the pillar" (fewer hospitals = bigger supply
   gap), the rank is flipped.
3. A pillar's score is the average of its inputs' ranks, ranked again from 0 to 100.
4. The total is a weighted average of the three pillars. Default weights are equal (1/3 each).
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

LABEL = "A screening tool, not investment advice."

# pillar -> list of (panel column, direction). +1: higher value = higher pillar score.
# Need = population (a stand-in until population aged 40+ is published by state). The self-reported
# diagnosis figures are NOT in the main score: "ever told by a health worker" partly measures access to
# testing, which rises with wealth, so it would tie Need to Ability to pay by construction.
PILLARS: dict[str, list[tuple[str, int]]] = {
    "need": [
        ("population_total", +1),
    ],
    "supply_gap": [
        ("fac_sec_tert_per_100k", -1),      # fewer hospitals per person = bigger gap
    ],
    "ability_to_pay": [
        ("insurance_any_avg_pct", +1),
        ("wealth_top2_pct", +1),
    ],
}
# Sensitivity check: Need also including self-reported high blood pressure and blood sugar (NDHS 2024,
# ages 15-49, "ever told by a health worker"). Shown on Under the hood and in the README, not used for ranking.
PILLARS_NEED_WITH_DIAGNOSES = {**PILLARS, "need": [
    ("population_total", +1),
    ("bp_ever_told_high_avg_pct", +1),
    ("sugar_ever_told_high_avg_pct", +1),
]}

PILLAR_NAMES = {"need": "Need", "supply_gap": "Supply gap", "ability_to_pay": "Ability to pay"}
EQUAL_WEIGHTS = {p: 1 / 3 for p in PILLARS}
TOP_N = 10


def percentile_rank(s: pd.Series) -> pd.Series:
    """0 = lowest state, 100 = highest. Ties share the average rank."""
    if s.isna().any():
        raise ValueError(f"{s.name} has missing values; cannot rank")
    n = len(s)
    return (s.rank(method="average") - 1) / (n - 1) * 100


def add_derived_inputs(panel: pd.DataFrame) -> pd.DataFrame:
    """Simple averages of the women's and men's figures (each survey reports them separately)."""
    p = panel.copy()
    p["bp_ever_told_high_avg_pct"] = (p.bp_ever_told_high_women_pct + p.bp_ever_told_high_men_pct) / 2
    p["sugar_ever_told_high_avg_pct"] = (p.sugar_ever_told_high_women_pct + p.sugar_ever_told_high_men_pct) / 2
    p["insurance_any_avg_pct"] = (p.insurance_any_women_pct + p.insurance_any_men_pct) / 2
    return p


def pillar_scores(panel: pd.DataFrame, pillars: dict = PILLARS) -> pd.DataFrame:
    """Return one row per state with each input's rank and each pillar's 0-100 score."""
    p = add_derived_inputs(panel)
    out = p[["state", "state_code", "zone"]].copy()
    for pillar, inputs in pillars.items():
        ranks = []
        for col, direction in inputs:
            r = percentile_rank(p[col] * direction)
            out[f"rank_{col}"] = r.round(1)
            ranks.append(r)
        out[f"score_{pillar}"] = percentile_rank(pd.concat(ranks, axis=1).mean(axis=1)).round(1)
    return out


def total_score(scores: pd.DataFrame, weights: dict[str, float] = EQUAL_WEIGHTS) -> pd.Series:
    w = normalise(weights)
    return sum(scores[f"score_{p}"] * w[p] for p in PILLARS)


def normalise(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("weights must sum to more than zero")
    return {k: v / total for k, v in weights.items()}


def build_scorecard(panel: pd.DataFrame, weights: dict[str, float] = EQUAL_WEIGHTS,
                    pillars: dict = PILLARS) -> pd.DataFrame:
    sc = pillar_scores(panel, pillars)
    sc["score_total"] = total_score(sc, weights).round(1)
    sc["rank"] = sc.score_total.rank(ascending=False, method="min").astype(int)
    sc["label"] = LABEL
    return sc.sort_values("rank").reset_index(drop=True)


def weight_grid(low: float = 0.2, high: float = 0.5, step: float = 0.05) -> list[dict[str, float]]:
    """Every combination of pillar weights from `low` to `high` in `step`s, normalised to sum to 1.
    Combinations that become identical after normalising are kept once."""
    vals = np.round(np.arange(low, high + step / 2, step), 4)
    seen, grid = set(), []
    for combo in itertools.product(vals, repeat=len(PILLARS)):
        w = normalise(dict(zip(PILLARS, combo)))
        key = tuple(round(v, 6) for v in w.values())
        if key not in seen:
            seen.add(key)
            grid.append(w)
    return grid


def stress_test(panel: pd.DataFrame, top_n: int = TOP_N, pillars: dict = PILLARS) -> pd.DataFrame:
    """Re-run the total over the weight grid. For each state: share of weightings that put it in
    the top `top_n`, and its best and worst rank. A state that stays near the top under most
    weightings is a robust finding."""
    sc = pillar_scores(panel, pillars)
    grid = weight_grid()
    ranks = pd.DataFrame({i: total_score(sc, w).rank(ascending=False, method="min")
                          for i, w in enumerate(grid)})
    res = pd.DataFrame({
        "state": sc.state,
        f"share_in_top{top_n}_pct": ((ranks <= top_n).mean(axis=1) * 100).round(0),
        "best_rank": ranks.min(axis=1).astype(int),
        "worst_rank": ranks.max(axis=1).astype(int),
        "median_rank": ranks.median(axis=1),
    })
    res["n_weightings"] = len(grid)
    res["label"] = LABEL
    return res.sort_values([f"share_in_top{top_n}_pct", "median_rank"], ascending=[False, True]).reset_index(drop=True)
