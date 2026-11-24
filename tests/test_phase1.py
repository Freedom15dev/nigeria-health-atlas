"""Phase 1 tests: state names, de-duplication, validation rules, transcription."""
import pandas as pd
import pytest

from clean import dedupe_by_distance, haversine_m
from common import MANUAL, load_states, to_official_state
from validate import check_pillars, check_panel_rows, check_payer_mix, check_ranges, check_register


# ---------- state names (data trap 1) ----------

@pytest.mark.parametrize("raw, official", [
    ("Fct", "Federal Capital Territory"),
    ("..FCT Abuja", "Federal Capital Territory"),
    ("FCT-Abuja", "Federal Capital Territory"),
    ("Federal Capital", "Federal Capital Territory"),
    ("Nassarawa", "Nasarawa"),
    ("Akwa-Ibom", "Akwa Ibom"),
    ("Cross-River", "Cross River"),
    ("plateau", "Plateau"),
    ("Lagos State", "Lagos"),
])
def test_state_aliases(raw, official):
    assert to_official_state(pd.Series([raw])).iloc[0] == official


def test_unknown_state_name_raises():
    with pytest.raises(ValueError):
        to_official_state(pd.Series(["Atlantis"]))


def test_lookup_has_37_units():
    s = load_states()
    assert len(s) == 37 and s.state_code.is_unique


def test_every_source_name_column_is_complete_and_joins():
    s = load_states()
    name_cols = [c for c in s.columns if c.startswith("name_")]
    assert {"name_grid3_hf", "name_ndhs_api", "name_ndhs_pdf", "name_geoboundaries"} <= set(name_cols)
    for c in name_cols:
        assert (s[c] != "").all(), c
        assert (to_official_state(s[c]) == s["state"]).all(), c
    assert s.loc[s.state == "Federal Capital Territory", "display_name"].item() == "FCT"
    assert to_official_state(pd.Series(["Abuja Federal Capital Territory"])).item() == "Federal Capital Territory"


# ---------- de-duplication (data trap 3) ----------

def _fac(name, lat, lon):
    return {"state": "Kano", "lga": "Nassarawa", "facility_name": name, "latitude": lat, "longitude": lon}


def test_haversine_known_distance():
    # 0.001 degrees of latitude is about 111 m
    assert 105 < haversine_m(12.0, 8.5, 12.001, 8.5) < 117


def test_dedupe_drops_close_same_name_keeps_far():
    df = pd.DataFrame([
        _fac("Gwagwarwa PHC", 12.0000, 8.5000),
        _fac("gwagwarwa  P.H.C", 12.0003, 8.5000),   # ~33 m away, same name after normalising -> drop
        _fac("Gwagwarwa PHC", 12.0100, 8.5000),      # ~1.1 km away -> keep
        _fac("Other Clinic", 12.0000, 8.5000),       # different name -> keep
    ])
    kept, dropped = dedupe_by_distance(df)
    assert len(dropped) == 1 and len(kept) == 3


# ---------- validation rules ----------

def _panel(n=37):
    s = load_states().head(n)
    return pd.DataFrame({"state": s.state, "state_code": s.state_code, "population_total": 1_000_000,
                         "insurance_any_men_pct": 5.0})


def test_validate_flags_missing_state():
    errs = check_panel_rows(_panel(36), load_states())
    assert any("36 rows" in e for e in errs) and any("missing" in e for e in errs)


def test_validate_passes_full_panel_rows():
    assert check_panel_rows(_panel(), load_states()) == []


def test_validate_flags_pillar_nulls():
    p = _panel()
    p.loc[0, "insurance_any_men_pct"] = None
    assert any("insurance_any_men_pct has nulls" in e for e in check_pillars(p))


def test_validate_flags_pct_out_of_range():
    p = _panel()
    p.loc[3, "insurance_any_men_pct"] = 140
    assert check_ranges(p)


def test_validate_register_needs_source(tmp_path):
    from load_register import COLUMNS
    good = {"specialty": "kidney", "state": "Bauchi", "facility_name": "X", "ownership": "public",
            "item": "dialysis machine", "count": "4", "status": "working", "gap_type": "unknown",
            "evidence_note": "n", "source_url": "https://example.org", "source_type": "news",
            "source_date": "2025-01-01", "date_accessed": "2026-11-24"}
    f = tmp_path / "reg.csv"
    pd.DataFrame([good], columns=COLUMNS).to_csv(f, index=False)
    assert check_register(f) == []
    pd.DataFrame([good, {**good, "source_url": ""}], columns=COLUMNS).to_csv(f, index=False)
    assert any("no source_url" in e for e in check_register(f))
    pd.DataFrame([{**good, "gap_type": "money"}], columns=COLUMNS).to_csv(f, index=False)
    assert any("gap_type" in e for e in check_register(f))
    pd.DataFrame([{**good, "state": "Bauchi State"}], columns=COLUMNS).to_csv(f, index=False)
    assert any("official name" in e for e in check_register(f))


def test_validate_payer_mix_must_sum_to_one(tmp_path):
    f = tmp_path / "a.yaml"
    f.write_text("payer_mix:\n  out_of_pocket: {value: 0.7}\n  nhia: {value: 0.2}\n")
    assert check_payer_mix(f)
    f.write_text("payer_mix:\n  out_of_pocket: {value: 0.7}\n  nhia: {value: 0.3}\n")
    assert check_payer_mix(f) == []


# ---------- FR395 transcription spot-checks (values read from the PDF text) ----------

@pytest.mark.parametrize("state, table, indicator, value", [
    ("Kano", "19.1.1", "blood_pressure_ever_told_high_pct", 12.4),
    ("Lagos", "19.1.2", "blood_pressure_ever_measured_pct", 79.6),
    ("Federal Capital Territory", "19.1.1", "blood_pressure_ever_measured_pct", 58.2),
    ("Niger", "19.2.1", "blood_sugar_ever_told_high_pct", 0.1),
])
def test_ndhs_transcription(state, table, indicator, value):
    m = pd.read_csv(MANUAL / "ndhs2024_state.csv", dtype={"table": str})
    row = m[(m.state == state) & (m.table == table) & (m.indicator == indicator)]
    assert len(row) == 1 and row.value.iloc[0] == value
