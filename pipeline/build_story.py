"""Phase 7: fill the story templates with numbers computed from data.

  story/README.md.tmpl    -> README.md
  story/linkedin.md.tmpl  -> exports/posts/linkedin.md
  story/x_thread.md.tmpl  -> exports/posts/x_thread.md
  all numbers             -> exports/story_numbers.csv (analyst pack: every figure the text quotes)

The templates hold only {placeholders} for figures (tests/test_story.py fails if a number is typed in),
so every number in the README and posts comes from src/story_numbers.py. A missing placeholder stops
the run rather than printing a blank.
"""
import string
import sys

import pandas as pd

from common import EXPORTS, ROOT

sys.path.insert(0, str(ROOT / "src"))
from story_numbers import story_numbers  # noqa: E402

STORY = ROOT / "story"
OUTPUTS = {"README.md.tmpl": ROOT / "README.md",
           "linkedin.md.tmpl": EXPORTS / "posts" / "linkedin.md",
           "x_thread.md.tmpl": EXPORTS / "posts" / "x_thread.md"}


def placeholders(text: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def render(text: str, numbers: dict[str, str]) -> str:
    missing = placeholders(text) - set(numbers)
    if missing:
        raise SystemExit(f"story placeholders with no number: {sorted(missing)}")
    return text.format_map(numbers)


def main() -> None:
    n = story_numbers()
    for tmpl, out in OUTPUTS.items():
        out.parent.mkdir(parents=True, exist_ok=True)
        text = render((STORY / tmpl).read_text(encoding="utf-8"), n)
        out.write_text(text, encoding="utf-8")
    pd.DataFrame(sorted(n.items()), columns=["key", "value"]).to_csv(EXPORTS / "story_numbers.csv", index=False)
    print(f"  story: README.md and {len(OUTPUTS) - 1} post drafts written; {len(n)} numbers from data")


if __name__ == "__main__":
    main()
