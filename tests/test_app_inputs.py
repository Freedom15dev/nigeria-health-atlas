"""Phase 5 tests: the pieces the app relies on (headline cards, map, story sentences)."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import story  # noqa: E402
from fetch_geoboundaries import _signed_area, rewind_for_plotly  # noqa: E402
from validate import check_headline_figures  # noqa: E402


def test_headline_cards_are_ranges_built_from_the_csv():
    hf = pd.read_csv(ROOT / "data" / "manual" / "headline_figures.csv", dtype=str, keep_default_na=False)
    cards = {c["card"]: c for c in story.headline_cards(hf)}
    main = hf[hf.role == "main"].assign(v=lambda d: d.figure.astype(float))
    lo, hi = main[main.card == "1"].v.min(), main[main.card == "1"].v.max()
    assert cards["1"]["big"] == f"{lo:,.0f}–{hi:,.0f}%"
    assert cards["3"]["big"].endswith("+")          # "over 200"
    assert cards["4"]["big"].startswith("₦")


def test_headline_check_catches_missing_source(tmp_path):
    hf = pd.read_csv(ROOT / "data" / "manual" / "headline_figures.csv", dtype=str, keep_default_na=False)
    assert check_headline_figures(ROOT / "data" / "manual" / "headline_figures.csv") == []
    hf.loc[0, "url"] = ""
    p = tmp_path / "h.csv"
    hf.to_csv(p, index=False)
    assert check_headline_figures(p)


def test_rewind_makes_outer_rings_clockwise_and_holes_anticlockwise():
    outer_ccw = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]      # RFC 7946 order
    hole_cw = [[0.2, 0.2], [0.2, 0.8], [0.8, 0.8], [0.8, 0.2], [0.2, 0.2]]
    g = rewind_for_plotly({"type": "Polygon", "coordinates": [outer_ccw, hole_cw]})
    assert _signed_area(g["coordinates"][0]) < 0 and _signed_area(g["coordinates"][1]) > 0


def test_breakeven_sentence_never_invents_a_number():
    s = story.breakeven_sentence({"breakeven_capacity_used": float("inf"), "average_price_ngn": 10_000,
                                  "variable_cost_per_session_ngn": 15_000, "capacity_used": 0.5,
                                  "breakeven_price_ngn": 30_000})
    assert "isn't reachable" in s and "₦10,000" in s and "₦15,000" in s


def test_main_gap_type_is_unknown_without_evidence():
    assert story.main_gap_type(pd.Series({"gap_equipment": 0, "gap_workforce": 0, "gap_systems": 0})) == "unknown"
    assert story.main_gap_type(pd.Series({"gap_equipment": 1, "gap_workforce": 0, "gap_systems": 3})) == "systems"
