"""The CLI's own texts (section ``cli`` of the catalogs): every key it uses exists, and every
key of the section is used. Keys are written out in the source for this test to find them."""

import re
from pathlib import Path

import primum_cli
from primum_cli.messages import Catalog

SOURCE = Path(primum_cli.__file__).resolve().parent
KEY_USES = (re.compile(r'\.text\(\s*"([\w.]+)"'), re.compile(r'"(severity\.\w+)"'))


def _used_keys() -> set[str]:
    used: set[str] = set()
    for path in SOURCE.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in KEY_USES:
            used.update(pattern.findall(text))
    return used


def test_the_cli_uses_every_key_of_its_section_and_only_keys_that_exist() -> None:
    keys = set(Catalog.load("en").cli)

    used = _used_keys() | {"list.and"}  # read by the list formatting itself

    assert used - keys == set(), "keys used by the CLI but missing in the catalogs"
    assert keys - used == set(), "keys in the catalogs that the CLI does not use"
