# Nigeria Health Atlas

**Where specialist care is missing in Nigeria, why it's missing, and what one centre could change.**

**Live app: https://nigeria-health-atlas.streamlit.app/**

A data project using public data. It maps where specialist care, kidney care (dialysis) and cancer care
(radiotherapy), is missing across Nigeria's 36 states and the FCT. It asks whether the gap is equipment,
workforce or systems, who can pay, and what one specialist centre could deliver in patients treated and
capacity used.

> The full write-up comes in the final phase. This page explains how the project is built and run.

## The app

A Streamlit app with seven pages:

| Page | What it shows |
|---|---|
| Home | four headline figures and a map of where to look first |
| State explorer | facilities, specialist capacity and ability to pay, state by state, with filters |
| Scorecard | an equal-weight state ranking (need, supply gap, ability to pay) and a weight stress-test |
| Specialist gaps | hand-built dialysis and radiotherapy registers: what is missing, and where sources disagree |
| Centre model | one illustrative dialysis or radiotherapy centre: patients treated, capacity used, break-even |
| Cost pressure | the naira, prices and health prices, month by month |
| Under the hood | sources, conflicting figures, data traps and limits |

```bash
python -m venv .venv && .venv/Scripts/activate     # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python pipeline/run_all.py        # fetch -> clean -> join -> score -> model -> charts -> validate
streamlit run app/Home.py
python -m pytest                  # tests, including hand-worked centre-model cases
```

## How it's built

```
config/        assumptions for the centre model (every input has a value, range and source) and story settings
data/raw/      untouched downloads, dated
data/manual/   hand-entered tables, with page numbers or source URLs
data/register/ the hand-built specialist capacity register (one row per fact, per source)
data/lookups/  state names as each source spells them; facility level mapping
data/processed/ what the app reads
pipeline/      fetch, clean, join, score, model, validate (python pipeline/run_all.py)
src/           scoring, centre model, charts, story sentences
app/           the Streamlit app
notebooks/     one walk-through notebook per phase
exports/       the chart pack (PNG) and tables
```

A GitHub Action re-runs the pipeline every Monday and commits only when a source has published something new.

## Rules the project follows

- Every number traces back to a source row with a date (`data/sources.yaml`).
- Where sources disagree, every figure is kept and the range is shown. Nothing is averaged away.
- Missing data stays "unknown". No gap is filled with a guess.
- All 37 units (36 states + FCT) appear in every state table.
- The scorecard is a screening tool. The centre model and its PPP structures are illustrations, not any
  real organisation's terms.
- Halima, who appears in the app, is an illustrative character, not a real person.

## Data

GRID3 health facilities and population (with WorldPop), the Nigeria Demographic and Health Survey 2024,
the World Bank, the Central Bank of Nigeria, the National Bureau of Statistics, geoBoundaries, and a
hand-built register of dialysis and radiotherapy capacity from peer-reviewed, government and news sources. Full list, with
licences and access dates, in [`data/sources.yaml`](data/sources.yaml) and on the app's Under the hood page.

Code: MIT licence (see `LICENSE`). Data: each source keeps its own licence.

---

Freedom Oboh · data analyst, Lagos

**This is a learning project using public data. It is not investment, medical or financial advice.**
