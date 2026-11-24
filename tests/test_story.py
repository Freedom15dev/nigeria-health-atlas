"""Phase 7: every number in the README and post drafts comes from code.

The templates in story/ may contain digits only inside {placeholders}, or in a short list of labels that
are names or fixed method words, not data (e.g. "NDHS 2024", "per 100,000", "8 in 10" as a threshold)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "src"))
from build_story import OUTPUTS, placeholders  # noqa: E402

# allowed digit tokens outside placeholders, with why
ALLOWED = {
    "2024": "survey name: NDHS 2024",
    "100": "score scale (0 to 100) and 'per 100,000'",
    "000": "part of '100,000' (per 100,000 people)",
    "0": "score scale (0 to 100)",
    "1": "'+1' in the explanation of a rank correlation; numbered steps",
    "10": "'top 10' in the stress-test question",
    "8": "'8 in 10' threshold in the distance chart's title rule",
    "2": "numbered sections and thread posts",
    "3": "numbered sections", "4": "numbered sections", "5": "numbered sections",
    "6": "numbered sections", "7": "thread post number",
    "15": "NDHS age range '15 to 49' (survey definition)",
    "49": "NDHS age range '15 to 49' (survey definition)",
    "40": "age-group label 'aged 40 and over' (a definition from the brief, not a figure)",
}


def outside_placeholders(text: str) -> str:
    return re.sub(r"\{[^{}]*\}", "", text)


def test_templates_have_no_typed_numbers():
    bad = {}
    for tmpl in OUTPUTS:
        text = outside_placeholders((ROOT / "story" / tmpl).read_text(encoding="utf-8"))
        text = re.sub(r"\(exports/[^)]*\)", "", text)          # image file names
        text = re.sub(r"chart\d+[a-z]?_\w+", "", text)
        tokens = set(re.findall(r"\d+", text)) - set(ALLOWED)
        if tokens:
            bad[tmpl] = sorted(tokens)
    assert not bad, f"typed numbers in templates: {bad}"


def test_every_placeholder_has_a_number():
    from story_numbers import story_numbers
    n = story_numbers()
    for tmpl in OUTPUTS:
        assert placeholders((ROOT / "story" / tmpl).read_text(encoding="utf-8")) <= set(n), tmpl


def test_readme_closes_with_the_disclaimer():
    text = (ROOT / "story" / "README.md.tmpl").read_text(encoding="utf-8").rstrip()
    assert text.endswith("**This is a learning project using public data. It is not investment, medical or "
                         "financial advice.**")
    assert " free" not in text.lower()
