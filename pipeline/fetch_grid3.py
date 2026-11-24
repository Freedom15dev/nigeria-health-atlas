"""GRID3 health facilities (v2.0) and the eHealth Africa cross-check file.

Both are on HDX, which blocks scripted downloads, so they are downloaded by hand
in a browser and saved to data/raw/. This step only checks they are present and
prints their checksums. To refresh: download the new file, save it with the new
pull date, update RAW_FILES in common.py and data/sources.yaml.
"""
import sys

from common import RAW_FILES, sha256


def main() -> None:
    for key in ("grid3_hf_v2", "ehealthafrica_hf"):
        p = RAW_FILES[key]
        if not p.exists():
            sys.exit(f"Missing raw file for {key}: {p}. Download it in a browser (see data/sources.yaml).")
        print(f"  {key}: {p.name} sha256={sha256(p)[:16]}...")


if __name__ == "__main__":
    main()
