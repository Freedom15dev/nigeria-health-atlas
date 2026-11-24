"""Run the whole pipeline: fetch -> load -> clean -> join -> build -> score -> export charts -> validate.

    python pipeline/run_all.py

Exits non-zero if validation fails.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import app_tables  # noqa: E402
import build  # noqa: E402
import build_story  # noqa: E402
import clean  # noqa: E402
import distance  # noqa: E402
import export_charts  # noqa: E402
import fetch_dhs  # noqa: E402
import fetch_geoboundaries  # noqa: E402
import fetch_grid3  # noqa: E402
import fetch_monthly  # noqa: E402
import fetch_nbs_cpi  # noqa: E402
import fetch_population  # noqa: E402
import fetch_wdi  # noqa: E402
import join_states  # noqa: E402
import load_manual  # noqa: E402
import load_register  # noqa: E402
import model_centre  # noqa: E402
import score  # noqa: E402
import validate  # noqa: E402


def main() -> None:
    for name, step in [("fetch_grid3", fetch_grid3.main), ("fetch_population", fetch_population.main),
                       ("fetch_dhs", fetch_dhs.main), ("fetch_wdi", fetch_wdi.main),
                       ("fetch_monthly", fetch_monthly.main), ("fetch_geoboundaries", fetch_geoboundaries.main),
                       ("fetch_nbs_cpi", fetch_nbs_cpi.main),
                       ("load_manual", load_manual.main), ("load_register", load_register.main)]:
        print(f"[{name}]")
        step()
    print("[clean]")
    steps = clean.main()
    print("[distance]")
    distance.main()
    print("[join_states]")
    join_states.main()
    print("[build]")
    build.main(steps)
    print("[score]")
    score.main()
    print("[model_centre]")
    model_centre.main()
    print("[app_tables]")
    app_tables.main()
    print("[export_charts]")
    export_charts.main()
    print("[build_story]")
    build_story.main()
    print("[validate]")
    validate.main()


if __name__ == "__main__":
    main()
