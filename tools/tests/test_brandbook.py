"""The brandbook page and the tokens say the same colors.

The page draws itself with its own CSS custom properties; every color they hold must be a
value of ``design/tokens/tokens.json``, so the page cannot drift from the tokens unseen.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRANDBOOK = ROOT / "design" / "brandbook.es.html"
TOKENS = ROOT / "design" / "tokens" / "tokens.json"

HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def _token_colors() -> set[str]:
    # Every color in the file is the value of a token: the file holds nothing else.
    return {match.lower() for match in HEX.findall(TOKENS.read_text(encoding="utf-8"))}


def _page_colors() -> set[str]:
    page = BRANDBOOK.read_text(encoding="utf-8")
    root = re.search(r":root\{(.*?)\}", page, re.DOTALL)
    assert root is not None, "the brandbook has no :root block"
    return {match.lower() for match in HEX.findall(root.group(1))}


def test_every_color_of_the_brandbook_is_a_token() -> None:
    assert _page_colors() - _token_colors() == set()
