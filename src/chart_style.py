"""House chart style, from DESIGN.md section 1: white background, navy text, green for the data,
orange only for "the one you picked" (the selected state, Halima, "your centre"), light grey
y-gridlines only. Used by the notebooks, the PNG exports and the Streamlit app."""
import pandas as pd
import plotly.graph_objects as go

# ---- palette (DESIGN.md section 1) ----
NAVY = "#0F1E33"          # text, headings, dark buttons
TEXT2 = "#4A5568"         # secondary text
GRID = "#E3E6EB"          # borders, gridlines
PANEL = "#F5F6F8"         # panel / BI page background
GREEN = "#3E9A63"         # main data colour
DARK_GREEN = "#1D6B44"    # links, active menu item, "higher"
LIGHT_GREEN = "#E3F1E6"   # active menu background
MAP_SCALE = ["#E3F1E6", "#B5DCC0", "#7FC296", "#3E9A63", "#1D6B44"]   # low -> high
MID_GREEN = MAP_SCALE[2]
PALE_GREEN = MAP_SCALE[1]
ORANGE = "#D9822B"        # highlight fill: selected state, Halima, "you"
ORANGE_TEXT = "#B4561A"   # highlight text on white
ORANGE_BG = "#FFF7EF"     # highlight background
GOOD, BAD = "#1D6B44", "#9B1C1C"
GAP_COLOURS = {"equipment": "#1D6B44", "workforce": "#D9822B", "systems": "#4A5568", "unknown": "#9AA5B4"}
MUTED = TEXT2             # kept for older code
FONT = "Inter, Segoe UI, Arial, sans-serif"
TITLE_FONT = "Space Grotesk, Inter, Segoe UI, Arial, sans-serif"
AUTHOR = "Freedom Oboh"


def style(fig: go.Figure, title: str, subtitle: str, source: str, height: int = 520,
          x_title: str | None = None, y_title: str | None = None, x_grid: bool = False) -> go.Figure:
    """Title = the finding in plain words; subtitle = the measure; source line at the bottom.
    Axes size their own margins, so long state names are never cut off."""
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family=FONT, color=NAVY, size=13),
        title=dict(text=f"<b>{title}</b><br><span style='font-size:13px;color:{MUTED}'>{subtitle}</span>",
                   x=0.01, xanchor="left", yref="container", y=1, yanchor="top",
                   pad=dict(t=16), font=dict(size=17)),
        margin=dict(l=20, r=30, t=110 + 18 * subtitle.count("<br>"), b=95),
        height=height,
        hoverlabel=dict(bgcolor="white", font_color=NAVY),
    )
    if fig.layout.showlegend is None:
        fig.update_layout(showlegend=False)
    fig.update_xaxes(showgrid=x_grid, gridcolor=GRID, zeroline=False, linecolor=GRID, automargin=True,
                     title_standoff=10, **({"title_text": x_title} if x_title is not None else {}))
    fig.update_yaxes(showgrid=not x_grid, gridcolor=GRID, zeroline=False, automargin=True,
                     title_standoff=10, **({"title_text": y_title} if y_title is not None else {}))
    # Source line sits in the bottom margin, below the x-axis title, at a fixed pixel offset.
    fig.add_annotation(text=f"Source: {source} · Analysis: {AUTHOR}", xref="paper", yref="paper",
                       x=0, y=0, yshift=-62, yanchor="top", xanchor="left", showarrow=False,
                       font=dict(size=11, color=MUTED))
    return fig


def label_extremes(df: pd.DataFrame, x: str, y: str, name: str = "state", n: int = 4,
                   always: list[str] | None = None) -> pd.Series:
    """Text labels only for the n highest/lowest states on each axis (plus any named),
    so labels don't pile up. Every point still shows its name on hover."""
    keep = set(always or [])
    for col in (x, y):
        keep |= set(df.nsmallest(n, col)[name]) | set(df.nlargest(n, col)[name])
    return df[name].where(df[name].isin(keep), "")
