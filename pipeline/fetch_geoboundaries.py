"""geoBoundaries NGA ADM1 (state boundaries) for the Home page map.

Raw:       data/raw/geoboundaries_nga_adm1_simplified_<pull date>.geojson (+ the API metadata)
Processed: data/processed/nga_states.geojson, with two properties per state:
           state (official name, the join key) and display_name (e.g. "FCT").

The boundaries are geoBoundaries' copy of GRID3's state boundaries, CC BY 4.0 (see sources.yaml).
If no raw file exists yet, the current release is downloaded once; later runs reuse the
dated raw file, so a weekly run never creates a new one unless the raw file is removed.
"""
import json
import sys

import pandas as pd
import requests

from common import PROCESSED, RAW, load_states, to_official_state, today

API = "https://www.geoboundaries.org/api/current/gbOpen/NGA/ADM1/"
PREFIX = "geoboundaries_nga_adm1"


def raw_paths():
    shapes = sorted(RAW.glob(f"{PREFIX}_simplified_*.geojson"))
    meta = sorted(RAW.glob(f"{PREFIX}_metadata_*.json"))
    return (shapes[-1] if shapes else None), (meta[-1] if meta else None)


def download() -> None:
    meta = requests.get(API, timeout=60).json()
    gj = requests.get(meta["simplifiedGeometryGeoJSON"], timeout=120)
    gj.raise_for_status()
    (RAW / f"{PREFIX}_simplified_{today()}.geojson").write_bytes(gj.content)
    (RAW / f"{PREFIX}_metadata_{today()}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


def _signed_area(ring) -> float:
    return sum(x0 * y1 - x1 * y0 for (x0, y0, *_), (x1, y1, *_) in zip(ring, ring[1:]))


def rewind_for_plotly(geom: dict) -> dict:
    """Plotly's geo maps (d3-geo) need outer rings clockwise and holes anticlockwise, the opposite
    of the GeoJSON standard (RFC 7946) that geoBoundaries follows. Without this, each state fills
    the whole world except itself."""
    def fix(poly):
        return [ring if (_signed_area(ring) < 0) == (i == 0) else ring[::-1] for i, ring in enumerate(poly)]
    if geom["type"] == "Polygon":
        return {**geom, "coordinates": fix(geom["coordinates"])}
    if geom["type"] == "MultiPolygon":
        return {**geom, "coordinates": [fix(p) for p in geom["coordinates"]]}
    return geom


def process(shapes_path) -> dict:
    gj = json.loads(shapes_path.read_text(encoding="utf-8"))
    names = pd.Series([f["properties"]["shapeName"] for f in gj["features"]])
    official = to_official_state(names)  # raises if any name doesn't join to the lookup
    display = load_states().set_index("state")["display_name"]
    if len(gj["features"]) != 37 or official.nunique() != 37:
        sys.exit(f"geoBoundaries: expected 37 distinct states, got {official.nunique()}")
    for f, st in zip(gj["features"], official):
        f["geometry"] = rewind_for_plotly(f["geometry"])
        f["properties"] = {"state": st, "display_name": display[st],
                           "shape_name": f["properties"]["shapeName"], "iso": f["properties"]["shapeISO"]}
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "nga_states.geojson").write_text(json.dumps(gj), encoding="utf-8")
    return {"features": len(gj["features"]), "joined": int(official.nunique())}


def main() -> None:
    shapes, meta = raw_paths()
    if shapes is None:
        print("  no raw geoBoundaries file; downloading the current release")
        download()
        shapes, meta = raw_paths()
    m = json.loads(meta.read_text(encoding="utf-8")) if meta else {}
    out = process(shapes)
    print(f"  {shapes.name}: {out['features']} shapes, {out['joined']} of 37 states joined to the lookup "
          f"(licence: {m.get('boundaryLicense', 'see sources.yaml')})")


if __name__ == "__main__":
    main()
