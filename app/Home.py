"""Nigeria Health Atlas: Streamlit entry point.

    streamlit run app/Home.py

Builds the top menu (DESIGN.md section 2) and runs the chosen page from app/views/.
The app only reads data/processed/ and config/; it never calls an API.
"""
import sys
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parent
for p in (APP, APP.parent / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

st.set_page_config(page_title="Nigeria Health Atlas", page_icon=str(APP / "static" / "logo.svg"),
                   layout="wide", initial_sidebar_state="collapsed")
st.logo(str(APP / "static" / "logo_wordmark.svg"), size="large")

PAGES = [
    st.Page(APP / "views" / "home.py", title="Home", default=True),
    st.Page(APP / "views" / "explorer.py", title="State explorer", url_path="state-explorer"),
    st.Page(APP / "views" / "scorecard.py", title="Scorecard", url_path="scorecard"),
    st.Page(APP / "views" / "gaps.py", title="Specialist gaps", url_path="specialist-gaps"),
    st.Page(APP / "views" / "centre.py", title="Centre model", url_path="centre-model"),
    st.Page(APP / "views" / "cost.py", title="Cost pressure", url_path="cost-pressure"),
    st.Page(APP / "views" / "under_hood.py", title="Under the hood", url_path="under-the-hood"),
]
st.navigation(PAGES, position="top").run()
