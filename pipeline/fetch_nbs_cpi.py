"""NBS Consumer Price Index: the Health division (COICOP 06) and All Items, monthly.

Source: NBS microdata catalog 154 (monthly CPI releases). The release list is JSON; the newest
release's workbook (zip of XLSX + PDF, or a bare XLSX for older releases) is saved to data/raw/
with the pull date. A run downloads only when a newer release appears.

Reads sheet "Table2" (composite CPI, base 2024 = 100): one row per month, columns found by
header text ("All Items", "Health."). Writes data/processed/nbs_cpi_health.csv.

Caveats (also in sources.yaml and the app):
- From January 2025 NBS uses a new basket (COICOP 2018; health weight 6.06%). The 2023-2024
  values in Table2 are the old 2009-basket index rescaled to 2024 = 100: a splice, not one
  consistent basket. The break is flagged in the output (basket column).
- Recent months can be revised, so each run re-reads the whole latest workbook.
"""
import io
import json
import re
import sys
import zipfile

import openpyxl
import pandas as pd
import requests

from common import PROCESSED, RAW, today

CATALOG = "https://microdata.nigerianstat.gov.ng/index.php/metadata/export/154/json"
PREFIX = "nbs_cpi"
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun",
                                      "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def latest_release() -> dict:
    res = requests.get(CATALOG, timeout=60).json()["resources"]
    res = [r for r in res if "cpi report" in r["title"].lower()
           and str(r.get("filename", "")).lower().endswith((".zip", ".xlsx"))]
    return max(res, key=lambda r: r["dcdate"])


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower().replace("cpi report", "")).strip("_")


def ensure_raw() -> tuple:
    """Return (raw workbook path, release info). Downloads only if the latest release is new."""
    try:
        rel = latest_release()
    except Exception as e:  # offline: fall back to the newest file already saved
        print(f"  NBS catalog not reachable ({type(e).__name__}); using the latest saved release")
        rel = None
    if rel:
        ext = rel["filename"].rsplit(".", 1)[-1].lower()
        existing = sorted(RAW.glob(f"{PREFIX}_{slug(rel['title'])}_*.{ext}"))
        if existing:
            path = existing[-1]
            print(f"  {rel['title']} (released {rel['dcdate']}) already saved: {path.name}")
        else:
            r = requests.get(rel["filename"], timeout=180)
            r.raise_for_status()
            path = RAW / f"{PREFIX}_{slug(rel['title'])}_{today()}.{ext}"
            path.write_bytes(r.content)
            (RAW / f"{PREFIX}_{slug(rel['title'])}_release_{today()}.json").write_text(
                json.dumps({k: rel.get(k) for k in ("resource_id", "title", "dcdate", "filename")}, indent=1),
                encoding="utf-8")
            print(f"  downloaded {rel['title']} (released {rel['dcdate']}): {path.name}")
        return path, rel
    saved = sorted([*RAW.glob(f"{PREFIX}_*.zip"), *RAW.glob(f"{PREFIX}_*.xlsx")], key=lambda p: p.stat().st_mtime)
    if not saved:
        sys.exit("No NBS CPI workbook saved and the catalog is unreachable.")
    return saved[-1], None


def read_table2(path) -> pd.DataFrame:
    if path.suffix == ".zip":
        z = zipfile.ZipFile(path)
        name = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
        data = z.read(name)
    else:
        data = path.read_bytes()
    ws = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)["Table2"]
    rows = list(ws.iter_rows(values_only=True))
    header_i = next(i for i, r in enumerate(rows) if any(str(c).strip() == "Health." for c in r if c))
    header = [str(c).strip() if c else "" for c in rows[header_i]]
    c_all, c_health = header.index("All Items"), header.index("Health.")
    out, year = [], None
    for r in rows[header_i + 1:]:
        if isinstance(r[0], (int, float)) and r[0] > 1900:
            year = int(r[0])
        m = str(r[1] or "").strip().lower()[:3]
        if year and m in MONTHS and r[c_health] is not None:
            out.append({"month": pd.Timestamp(year, MONTHS[m], 1),
                        "all_items_index": float(r[c_all]), "health_index": float(r[c_health])})
    d = pd.DataFrame(out).sort_values("month")
    if d.month.duplicated().any() or d.empty:
        sys.exit("NBS Table2: unexpected layout (duplicate or no months)")
    return d


def main() -> None:
    path, rel = ensure_raw()
    d = read_table2(path)
    d["basket"] = d.month.map(lambda m: "new basket (2024=100)" if m >= pd.Timestamp(2025, 1, 1)
                              else "old 2009 basket, rescaled to 2024=100 by NBS")
    d["health_yoy_pct"] = (d.health_index / d.health_index.shift(12) - 1) * 100
    d["all_items_yoy_pct"] = (d.all_items_index / d.all_items_index.shift(12) - 1) * 100
    d["source_file"] = path.name
    d["release"] = rel["title"] if rel else ""
    d.to_csv(PROCESSED / "nbs_cpi_health.csv", index=False)
    print(f"  NBS CPI health index: {d.month.min():%Y-%m} to {d.month.max():%Y-%m}, {len(d)} months")


if __name__ == "__main__":
    main()
