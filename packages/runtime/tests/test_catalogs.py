"""The message catalogs in i18n/ (decision 0009): complete, consistent and used.

Every error code the runtime can raise has an entry in every language, every language has the
same keys and placeholders, and the page's UI strings exist and are all used.
"""

import json
import re
from pathlib import Path
from typing import TypeIs

import pytest

from primum_runtime.errors import ErrorCode

ROOT = Path(__file__).resolve().parents[3]
CATALOGS = ROOT / "i18n"
UI = ROOT / "packages" / "runtime" / "src" / "primum_runtime" / "ui"
DEFAULT = "en"
LANGUAGES = ("en", "es")
# Shown apart as technical detail, never inside a message (see i18n/README.md).
TECHNICAL_PARAMS = frozenset({"detail", "consumer", "fields"})
PLACEHOLDER = re.compile(r"\{(\w+)\}")
# How the page names UI keys: data-i18n="key" in the HTML and t("key") in the scripts.
UI_KEY_USES = (re.compile(r'data-i18n="([\w.]+)"'), re.compile(r'\bt\("([\w.]+)"'))

type Catalog = dict[str, dict[str, object]]


def _is_object(value: object) -> TypeIs[dict[str, object]]:
    return isinstance(value, dict)


def _load(language: str) -> Catalog:
    catalog: Catalog = json.loads((CATALOGS / f"{language}.json").read_text(encoding="utf-8"))
    return catalog


def _strings(catalog: Catalog) -> dict[str, str]:
    """Every string of a catalog by a path such as ``errors.hal.closed.hint``."""
    strings: dict[str, str] = {}
    for section, entries in catalog.items():
        for key, value in entries.items():
            fields = value if _is_object(value) else {"": value}
            for field, text in fields.items():
                assert isinstance(text, str), f"{section}.{key}: expected text"
                strings[".".join(filter(None, (section, key, field)))] = text
    return strings


def _placeholders(text: str) -> set[str]:
    return set(PLACEHOLDER.findall(text))


def _ui_keys_used_by_the_page() -> set[str]:
    used: set[str] = set()
    for path in [*UI.glob("*.html"), *UI.glob("*.js")]:
        text = path.read_text(encoding="utf-8")
        for pattern in UI_KEY_USES:
            used.update(pattern.findall(text))
    return used


@pytest.mark.parametrize("language", [lang for lang in LANGUAGES if lang != DEFAULT])
def test_every_language_has_the_same_strings_and_placeholders_as_the_default(
    language: str,
) -> None:
    default = _strings(_load(DEFAULT))
    other = _strings(_load(language))

    assert set(other) == set(default)
    mismatched = {
        path for path, text in default.items() if _placeholders(text) != _placeholders(other[path])
    }
    assert mismatched == set()


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_error_code_has_a_message_and_a_hint_and_nothing_else(language: str) -> None:
    errors = _load(language)["errors"]

    assert set(errors) == {code.value for code in ErrorCode}
    for code, entry in errors.items():
        assert _is_object(entry), code
        assert set(entry) == {"message", "hint"}, code
        assert all(entry.values()), code


@pytest.mark.parametrize("language", LANGUAGES)
def test_error_messages_never_embed_technical_params(language: str) -> None:
    strings = _strings(_load(language))

    embedded = {
        path: _placeholders(text) & TECHNICAL_PARAMS
        for path, text in strings.items()
        if path.startswith("errors.") and _placeholders(text) & TECHNICAL_PARAMS
    }
    assert embedded == {}


def test_the_page_uses_every_ui_key_and_only_keys_that_exist() -> None:
    ui = set(_load(DEFAULT)["ui"])

    used = _ui_keys_used_by_the_page()

    assert used - ui == set(), "keys used by the page but missing in the catalogs"
    assert ui - used == set(), "keys in the catalogs that the page does not use"
