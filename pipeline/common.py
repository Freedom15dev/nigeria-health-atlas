"""Shared paths and helpers for the pipeline.

The one place where state names are matched (data trap 1).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANUAL = ROOT / "data" / "manual"
LOOKUPS = ROOT / "data" / "lookups"
REGISTER = ROOT / "data" / "register"
PROCESSED = ROOT / "data" / "processed"
EXPORTS = ROOT / "exports"
CONFIG = ROOT / "config"
SOURCES_YAML = ROOT / "data" / "sources.yaml"

# Manually downloaded raw files (HDX and dhsprogram.com block scripted downloads).
RAW_FILES = {
    "grid3_hf_v2": RAW / "grid3_nga_health_facilities_v2_0_2026-11-24.gpkg",
    "ehealthafrica_hf": RAW / "ehealthafrica_nga_health_facilities_2026-11-24.csv",
    "grid3_pop_v3": RAW / "grid3_worldpop_nga_population_v3_0_admin_2026-11-24.zip",
    "ndhs2024_fr395": RAW / "ndhs2024_fr395_final_report_2026-11-24.pdf",
}

UNKNOWN = "unknown"


def today() -> str:
    return dt.date.today().isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_sources() -> dict:
    with open(SOURCES_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------- state names ----------

def _key(name: str) -> str:
    s = str(name).lower().replace(".", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\bstate$", "", s).strip()
    return s.replace(" ", "")


def load_states() -> pd.DataFrame:
    return pd.read_csv(LOOKUPS / "states.csv", dtype=str, keep_default_na=False)


def state_name_map() -> dict[str, str]:
    """Map every known spelling (normalised) to the official state name: the official name,
    the display name, the name used in each source (name_* columns) and any other aliases."""
    s = load_states()
    name_cols = ["state", "display_name", *[c for c in s.columns if c.startswith("name_")]]
    m: dict[str, str] = {}
    for _, r in s.iterrows():
        for n in [*(r[c] for c in name_cols), *[a for a in r["aliases"].split("|") if a]]:
            k = _key(n.lstrip("."))
            if k in m and m[k] != r["state"]:
                raise ValueError(f"'{n}' maps to both {m[k]} and {r['state']}")
            m[k] = r["state"]
    return m


def to_official_state(names: pd.Series) -> pd.Series:
    """Return official state names. Raises if any name is not in the lookup."""
    m = state_name_map()
    out = names.map(lambda n: m.get(_key(n)))
    bad = sorted(set(names[out.isna()].astype(str)))
    if bad:
        raise ValueError(f"State names not in data/lookups/states.csv: {bad}")
    return out


# ---------- raw snapshots for API pulls ----------

def save_raw_if_changed(prefix: str, payload, content_for_compare) -> Path:
    """Write data/raw/<prefix>_<today>.json only if the content differs from the
    latest existing snapshot. Returns the path of the snapshot to use.
    Keeps weekly runs from creating new files (and commits) when nothing changed."""
    existing = sorted(RAW.glob(f"{prefix}_*.json"))
    new_sig = hashlib.sha256(json.dumps(content_for_compare, sort_keys=True).encode()).hexdigest()
    if existing:
        with open(existing[-1], encoding="utf-8") as f:
            old = json.load(f)
        if old.get("_signature") == new_sig:
            print(f"  unchanged since {existing[-1].name}; no new raw file")
            return existing[-1]
    path = RAW / f"{prefix}_{today()}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"_pulled": today(), "_signature": new_sig, "payload": payload}, f, indent=1)
    print(f"  saved {path.name}")
    return path


def latest_raw(prefix: str) -> Path:
    files = sorted(RAW.glob(f"{prefix}_*.json"))
    if not files:
        raise FileNotFoundError(f"No raw snapshot data/raw/{prefix}_*.json")
    return files[-1]
