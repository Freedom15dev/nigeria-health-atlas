"""Shared pieces for every page: fonts and CSS, cached loaders, page opening, cards, footer.

The app only reads data/processed/ (and config/). It never calls an API.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
for p in (ROOT / "src", ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import chart_style as cs  # noqa: E402

FOOTER_LEFT = "A learning project using public data. Not investment advice. · Freedom Oboh"
SCREENING = "A screening tool, not investment advice."


# ---------- loaders (cached) ----------

@st.cache_data(show_spinner=False)
def csv(name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(PROCESSED / name, **kw)


@st.cache_data(show_spinner=False)
def meta() -> dict:
    return json.loads((PROCESSED / "meta.json").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def geojson() -> dict:
    return json.loads((PROCESSED / "nga_states.geojson").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def assumptions(specialty: str = "kidney") -> dict:
    with open(ROOT / "config" / f"assumptions_{specialty}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def display_names() -> dict:
    return csv("states.csv").set_index("state").display_name.to_dict()


# ---------- look ----------

CSS = f"""
<style>
h1, h2, .big-number, .atlas-title {{ font-family: 'Space Grotesk', Inter, sans-serif !important; font-weight: 700 !important; color: {cs.NAVY}; }}
h1 {{ font-size: 2.0rem !important; line-height: 1.2 !important; }}
/* no sidebar rule: on phones Streamlit moves the top menu into the sidebar */
.block-container {{ padding-top: 4.2rem; max-width: 1180px; }}
/* top menu: current page light green with dark green text */
[data-testid="stTopNavLink"][aria-current="page"], [data-testid="stTopNavLink"]:has(> [aria-current="page"]) {{ background: {cs.LIGHT_GREEN}; }}
[data-testid="stTopNavLink"][aria-current="page"] span, [data-testid="stTopNavLink"] [aria-current="page"] span {{ color: {cs.DARK_GREEN} !important; font-weight: 600; }}
/* buttons and inputs at least 44px tall */
.stButton button, .stDownloadButton button, [data-testid="stPageLink"] a, .stSelectbox [data-baseweb="select"] > div,
.stNumberInput input {{ min-height: 44px; }}
.card {{ border: 1px solid {cs.GRID}; border-radius: 12px; padding: 18px 20px; background: #fff; height: 100%; }}
.card .label {{ color: {cs.TEXT2}; font-size: .85rem; font-weight: 500; }}
.card .big-number {{ font-size: 2.0rem; line-height: 1.15; margin: .25rem 0 .35rem 0; color: {cs.NAVY}; }}
.card .line {{ font-size: .92rem; color: {cs.NAVY}; }}
.card .src {{ font-size: .75rem; color: {cs.TEXT2}; margin-top: .5rem; }}
.card.highlight {{ background: {cs.ORANGE_BG}; border-color: {cs.ORANGE}; }}
.card.highlight .big-number {{ color: {cs.ORANGE_TEXT}; }}
.card.measure {{ border: 2px solid {cs.NAVY}; }}
.note-orange {{ border: 1px solid {cs.ORANGE}; background: {cs.ORANGE_BG}; color: {cs.ORANGE_TEXT}; border-radius: 10px;
               padding: 8px 14px; font-size: .9rem; display: inline-block; margin-bottom: .5rem; }}
.orange-line {{ color: {cs.ORANGE_TEXT}; font-weight: 600; }}
.small-grey {{ color: {cs.TEXT2}; font-size: .85rem; }}
.badge {{ display:inline-block; background:{cs.ORANGE_BG}; color:{cs.ORANGE_TEXT}; border:1px solid {cs.ORANGE};
          border-radius: 999px; padding: 1px 10px; font-size: .75rem; font-weight: 600; }}
.step-num {{ color: {cs.ORANGE}; font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 1.4rem; }}
.bar-row {{ display:flex; align-items:center; gap:10px; margin:6px 0; font-size:.88rem; }}
.bar-row .name {{ width: 42%; color:{cs.NAVY}; }}
.bar-row .track {{ flex:1; background:{cs.GRID}; border-radius:6px; height:10px; position:relative; }}
.bar-row .fill {{ position:absolute; left:0; top:0; bottom:0; border-radius:6px; }}
.bar-row .val {{ width: 3.2rem; text-align:right; font-weight:600; }}
.progress {{ background:{cs.GRID}; border-radius:8px; height:12px; margin:.4rem 0 .6rem 0; }}
.progress > div {{ background:{cs.GREEN}; height:12px; border-radius:8px; }}
.footer {{ border-top: 1px solid {cs.GRID}; margin-top: 2.5rem; padding-top: .8rem; display:flex; flex-wrap:wrap;
           justify-content:space-between; gap:.5rem 2rem; font-size:.8rem; color:{cs.TEXT2}; }}
.footer .right {{ text-align:right; flex: 1 1 420px; }}
/* grey panels: keyed containers */
[class*="st-key-panel"] {{ background: {cs.PANEL}; border-radius: 12px; padding: 16px 18px; }}
[class*="st-key-white"] {{ background: #fff; border: 1px solid {cs.GRID}; border-radius: 12px; padding: 14px 16px; }}
[data-testid="stDataFrame"] {{ overflow-x: auto; }}
@media (max-width: 640px) {{
  h1 {{ font-size: 1.5rem !important; }}
  .footer .right {{ text-align:left; max-width:100%; }}
  .card .big-number {{ font-size: 1.6rem; }}
}}
</style>
"""

BI_CSS = f"""<style>
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{ background: {cs.PANEL}; }}
.block-container {{ max-width: 1320px; }}
</style>"""


def setup(bi: bool = False) -> None:
    st.html(CSS + (BI_CSS if bi else ""))


def opening(title: str, intro: str = "") -> None:
    st.title(title)
    if intro:
        st.markdown(intro)


def data_as_of(*keys: str) -> str:
    m = meta()["data_as_of"]
    return " · ".join(f"{k}: {m[k]}" for k in keys if k in m)


def footer(sources: str, as_of: str = "") -> None:
    built = meta().get("built", "")
    right = f"Sources: {html.escape(sources)}<br>" + (f"Data as of {html.escape(as_of)} · " if as_of else "") + f"pipeline built {built}"
    st.html(f'<div class="footer"><div>{FOOTER_LEFT}</div><div class="right">{right}</div></div>')


def card(label: str, big: str, line: str = "", src: str = "", kind: str = "") -> str:
    return (f'<div class="card {kind}"><div class="label">{html.escape(label)}</div>'
            f'<div class="big-number">{html.escape(big)}</div>'
            + (f'<div class="line">{line}</div>' if line else "")
            + (f'<div class="src">{src}</div>' if src else "") + "</div>")


def bar_rows(rows: list[tuple[str, float, float, str]]) -> str:
    """rows: (name, value, max, colour) -> simple horizontal bars in HTML."""
    out = []
    for name, v, vmax, colour in rows:
        w = 0 if v is None or pd.isna(v) or not vmax else max(0, min(100, 100 * v / vmax))
        val = "[—]" if v is None or pd.isna(v) else f"{v:,.0f}"
        out.append(f'<div class="bar-row"><div class="name">{html.escape(name)}</div><div class="track">'
                   f'<div class="fill" style="width:{w:.1f}%;background:{colour}"></div></div>'
                   f'<div class="val">{val}</div></div>')
    return "".join(out)


def download(df: pd.DataFrame, filename: str, label: str = "Download CSV", key: str | None = None) -> None:
    st.download_button(label, df.to_csv(index=False).encode("utf-8"), file_name=filename, mime="text/csv",
                       key=key or f"dl_{filename}")


def chart(fig, key: str | None = None, **kw):
    fig.update_layout(font_family=cs.FONT)
    return st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key, **kw)
