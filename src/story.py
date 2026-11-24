"""Story numbers: small functions that turn results into plain sentences and card values.

Every number in a sentence is read from data at run time. Nothing here types in a figure.
Used by the Streamlit app (and later the README).
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
STORY = ROOT / "config" / "story.yaml"
UNKNOWN = "[—]"   # DESIGN.md: show this, never a made-up number


# ---------- formatting ----------

def naira(v: float, short: bool = False) -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return UNKNOWN
    sign = "−" if v < 0 else ""
    v = abs(v)
    if short:
        for div, unit in ((1e12, "tn"), (1e9, "bn"), (1e6, "m"), (1e3, "k")):
            if v >= div:
                return f"{sign}₦{v / div:,.{0 if v / div >= 100 else 1}f}{unit}".replace(".0" + unit, unit)
    return f"{sign}₦{v:,.0f}"


def number(v: float, unit: str = "") -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return UNKNOWN
    if unit.startswith("NGN"):
        return naira(v, short=True)
    s = f"{v:,.1f}".rstrip("0").rstrip(".") if v != int(v) else f"{int(v):,}"
    return s + ("%" if unit == "%" else "")


def short_state(name: str) -> str:
    return "FCT" if name == "Federal Capital Territory" else name


# ---------- Halima ----------

def halima() -> dict:
    with open(STORY, encoding="utf-8") as f:
        return yaml.safe_load(f)["halima"]


def halima_intro(assumptions: dict) -> str:
    """Two sentences. The price comes from the centre model's assumptions (sourced)."""
    h = halima()
    price = assumptions["prices"]["price_out_of_pocket_ngn"]["value"]
    lo = assumptions["capacity"]["sessions_per_patient_per_week"]["low"]
    hi = assumptions["capacity"]["sessions_per_patient_per_week"]["high"]
    return (f"Halima is {h['age']}, a {h['occupation']} in {short_state(h['state'])}. Her kidneys have failed, so "
            f"she needs dialysis {lo}–{hi} times a week for life, at about {naira(price)} a session at a "
            f"public hospital: {naira(price * lo * 52, short=True)}–{naira(price * hi * 52, short=True)} a year "
            f"for her family.")


# ---------- headline cards (Home) ----------

def headline_cards(hf: pd.DataFrame) -> list[dict]:
    """One dict per card: label, big number (the range of the 'main' rows), one line (from the
    'context' rows, or the sources' spread), and the source rows."""
    cards = []
    hf = hf.assign(figure=pd.to_numeric(hf.figure))
    for card, g in hf.groupby("card", sort=True):
        main = g[g.role == "main"]
        unit = main.unit.iloc[0]
        lo, hi = main.figure.min(), main.figure.max()
        top_q = main.loc[main.figure.idxmax(), "qualifier"]
        if unit.startswith("NGN"):
            big = f"{naira(lo, True)}–{naira(hi, True).lstrip('₦')}"
        else:
            big = f"{lo:,.0f}–{hi:,.0f}" + ("%" if unit == "%" else "") + ("+" if top_q == "over" else "")
        lines = [r.line.format(figure=number(r.figure), qualifier=r.qualifier).strip()
                 for r in g[g.role == "context"].itertuples()]
        if not lines:
            lines = [f"{len(main)} sources, {main.source_date.min()[:4]}–{main.source_date.max()[:4]}: "
                     "they don't agree"]
        cards.append({"card": card, "label": main.label.iloc[0], "big": big, "line": "; ".join(lines),
                      "rows": g.to_dict("records")})
    return cards


# ---------- register sentences ----------

def public_dialysis_sentence(by_state: pd.DataFrame) -> str:
    yes = (by_state.public_dialysis_working == "yes").sum()
    unk = (by_state.public_dialysis_working == "unknown").sum()
    no = (by_state.public_dialysis_working == "reported not working").sum()
    return (f"{yes} of {len(by_state)} states have a public dialysis unit reported working in the register; "
            f"in {no} the only reports say it isn't working, and for {unk} the register has no "
            f"evidence either way.")


def main_gap_type(row: pd.Series) -> str:
    """The most-cited known gap type in a state's register rows, or 'unknown'."""
    counts = {g: int(row.get(f"gap_{g}", 0) or 0) for g in ("equipment", "workforce", "systems")}
    best = max(counts.values())
    if best == 0:
        return "unknown"
    return " / ".join(g for g, n in counts.items() if n == best)


def machines_range(by_state: pd.DataFrame) -> tuple[float, float, int]:
    """Working dialysis machines across states with a count: (low, high, number of states)."""
    has = by_state.dropna(subset=["machines_working_low"])
    return has.machines_working_low.sum(), has.machines_working_high.sum(), len(has)


# ---------- centre model sentence ----------

def breakeven_sentence(r: dict) -> str:
    be = r["breakeven_capacity_used"]
    if not math.isfinite(be):
        return (f"Break-even isn't reachable at this price: each session brings in "
                f"{naira(r['average_price_ngn'])} but costs {naira(r['variable_cost_per_session_ngn'])} in "
                f"consumables, power and water alone.")
    if be > 1:
        return (f"Break-even isn't reachable: it would need {be:.0%} of slots filled, more than the centre has. "
                f"The price that covers running costs at this level of use is {naira(r['breakeven_price_ngn'])}.")
    return (f"The centre covers its running costs once it uses {be:.0%} of its slots "
            f"(it uses {r['capacity_used']:.0%} now).")
