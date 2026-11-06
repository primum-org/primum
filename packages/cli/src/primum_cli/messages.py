"""The text of what ``core`` reports, in the user's language (decision 0009).

Codes and params come from ``core``; the message and the hint of each code, and the CLI's own
words, come from the catalogs in ``i18n/`` (copied into ``generated/i18n/``). A list param is
joined for the language ("17, 22 and 27", "17, 22 y 27").
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypeIs

from primum_core.errors import Issue, ParamValue

CATALOGS = Path(__file__).resolve().parent / "generated" / "i18n"
LANGUAGES = ("en", "es")
DEFAULT_LANGUAGE = "en"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _is_object(value: object) -> TypeIs[dict[str, object]]:
    return isinstance(value, dict)


def _texts(value: object) -> dict[str, str]:
    if not _is_object(value):
        return {}
    return {key: text for key, text in value.items() if isinstance(text, str)}


@dataclass(frozen=True)
class Catalog:
    """The messages of one language."""

    errors: Mapping[str, Mapping[str, str]]
    cli: Mapping[str, str]

    @classmethod
    def load(cls, language: str) -> "Catalog":
        document: object = json.loads((CATALOGS / f"{language}.json").read_text(encoding="utf-8"))
        if not _is_object(document):
            raise ValueError(f"catalog {language} is not an object")
        errors = document.get("errors")
        entries = errors.items() if _is_object(errors) else ()
        return cls({code: _texts(entry) for code, entry in entries}, _texts(document.get("cli")))

    def text(self, key: str, **params: ParamValue) -> str:
        """One of the CLI's own texts."""
        return self._fill(self.cli[key], params)

    def describe(self, issue: Issue) -> tuple[str, str]:
        """The message and the hint of ``issue``."""
        entry = self.errors.get(issue.code)
        if entry is None:  # a code newer than the catalog: say so, never hide it
            return self.text("issue.unknown", code=issue.code), ""
        return self._fill(entry["message"], issue.params), self._fill(entry["hint"], issue.params)

    def _fill(self, template: str, params: Mapping[str, ParamValue]) -> str:
        def value(match: re.Match[str]) -> str:
            name = match[1]
            return self._format(params[name]) if name in params else match[0]

        return PLACEHOLDER.sub(value, template)

    def _format(self, value: ParamValue) -> str:
        if not isinstance(value, tuple):
            return str(value)
        items = [str(item) for item in value]
        if len(items) < 2:
            return "".join(items)
        return f"{', '.join(items[:-1])} {self.cli['list.and']} {items[-1]}"
