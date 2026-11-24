"""Smoke test: open every page of the app headlessly and check it renders without errors.

    python tests/smoke_test_app.py

Used by the weekly GitHub Action after the pipeline runs, so a data update that breaks a page
turns the run red and nothing is committed.
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app" / "Home.py")
PAGES = ["views/home.py", "views/explorer.py", "views/scorecard.py", "views/gaps.py", "views/centre.py",
         "views/cost.py", "views/under_hood.py"]


def main() -> None:
    failed = []
    for page in PAGES:
        at = AppTest.from_file(APP, default_timeout=180)
        at.run()
        if page != PAGES[0]:
            at.switch_page(page).run()
        problems = [e.value for e in at.exception] + [e.value for e in at.error]
        print(f"  {page:22} {'ok' if not problems else problems[:2]}")
        if problems or not at.title:
            failed.append(page)
    # the cancer side of each specialty switch
    for page, key, value in [("views/gaps.py", "gap_spec", "Cancer care"),
                             ("views/centre.py", "cm_kind", "Radiotherapy centre"),
                             ("views/explorer.py", "ex_spec", "Cancer")]:
        at = AppTest.from_file(APP, default_timeout=180)
        at.run()
        at.switch_page(page)
        at.session_state[key] = value
        at.run()
        problems = [e.value for e in at.exception] + [e.value for e in at.error]
        print(f"  {page:22} [{value}] {'ok' if not problems else problems[:2]}")
        if problems:
            failed.append(f"{page} [{value}]")
    if failed:
        sys.exit(f"Pages with errors: {failed}")
    print("  all pages render")


if __name__ == "__main__":
    main()
