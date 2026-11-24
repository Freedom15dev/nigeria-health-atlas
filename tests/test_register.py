"""Phase 3 tests: the register summary keeps conflicting sources as a range."""
import pandas as pd

from load_register import COLUMNS, summarise_by_state


def _row(**kw):
    base = {"specialty": "kidney", "state": "Bauchi", "facility_name": "Hospital A", "ownership": "public",
            "item": "dialysis machine", "count": "", "status": "working", "gap_type": "unknown",
            "evidence_note": "n", "source_url": "https://example.org", "source_type": "news",
            "source_date": "2025-01-01", "date_accessed": "2026-11-24"}
    return {**base, **kw}


def test_conflicting_counts_become_a_range_not_an_average():
    r = pd.DataFrame([
        _row(count="4"),                                    # source 1: 4 working machines
        _row(count="8", source_url="https://other.org"),    # source 2 disagrees: 8
        _row(facility_name="Hospital B", count="2"),        # a second facility
    ], columns=COLUMNS)
    s = summarise_by_state(r).set_index("state").loc["Bauchi"]
    assert s.machines_working_low == 6 and s.machines_working_high == 10   # (4+2) to (8+2), never 7+2


def test_state_without_rows_is_no_evidence_not_zero():
    r = pd.DataFrame([_row(count="3")], columns=COLUMNS)
    s = summarise_by_state(r).set_index("state")
    assert len(s) == 37
    assert s.loc["Kano", "evidence"] == "no evidence found"
    assert pd.isna(s.loc["Kano", "machines_working_low"])


def test_public_not_working_is_reported():
    r = pd.DataFrame([_row(count="5", status="not working", gap_type="equipment")], columns=COLUMNS)
    s = summarise_by_state(r).set_index("state").loc["Bauchi"]
    assert s.public_dialysis_working == "reported not working" and s.gap_equipment == 1


def test_statewide_figure_is_a_separate_estimate_not_added():
    """Lagos-style case: hospitals report 7 + 6 + 3 = 16 working; a state-wide source says 18.
    The range is 16-18, not 34."""
    r = pd.DataFrame([
        _row(facility_name="H1", count="7"), _row(facility_name="H2", count="6"),
        _row(facility_name="H3", count="3"), _row(facility_name="", count="18"),
    ], columns=COLUMNS)
    s = summarise_by_state(r).set_index("state").loc["Bauchi"]
    assert (s.machines_working_low, s.machines_working_high) == (16, 18)


def test_zero_working_centres_is_not_a_working_centre():
    r = pd.DataFrame([_row(item="dialysis centre", count="0", status="working", facility_name="")], columns=COLUMNS)
    assert summarise_by_state(r).set_index("state").loc["Bauchi", "public_dialysis_working"] == "unknown"
