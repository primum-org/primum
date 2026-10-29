"""Generate design/tokens/tokens.css from design/tokens/tokens.json, the single source.

Every leaf becomes a CSS custom property named after its path (``font.size.md`` →
``--font-size-md``). Values under ``themes.<id>`` are emitted per theme: light on ``:root``
and ``[data-theme="light"]``, dark on ``[data-theme="dark"]`` and, when no theme is set,
following ``prefers-color-scheme``.

    uv run just gen         # write tokens.css
    uv run just gen-check   # fail if tokens.css is out of date (part of `just check`)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import TypeIs

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "design" / "tokens" / "tokens.json"
TARGET = ROOT / "design" / "tokens" / "tokens.css"

HEADER = (
    "/* Primum design tokens. GENERATED from design/tokens/tokens.json by "
    "tools/gen_tokens.py: do not edit. */"
)
SKIPPED_KEYS = frozenset({"meta", "themes"})
THEMES = ("light", "dark")

type Declarations = list[tuple[str, str]]


class TokenError(ValueError):
    """The tokens file does not have the expected shape."""


def _is_object(value: object) -> TypeIs[dict[str, object]]:
    return isinstance(value, dict)


def _flatten(node: object, path: tuple[str, ...]) -> Declarations:
    if isinstance(node, str):
        return [("--" + "-".join(path), node)]
    if not _is_object(node):
        raise TokenError(f"{'.'.join(path)}: expected a string or an object")
    declarations: Declarations = []
    for key, child in node.items():
        declarations.extend(_flatten(child, (*path, key)))
    return declarations


def _block(selector: str, declarations: Declarations, indent: str = "") -> str:
    lines = [f"{indent}{selector} {{"]
    lines += [f"{indent}  {name}: {value};" for name, value in declarations]
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def render(tokens: object) -> str:
    """Return the CSS for a parsed tokens document."""
    if not _is_object(tokens):
        raise TokenError("the tokens document must be an object")
    themes = tokens.get("themes")
    if not _is_object(themes) or set(themes) != set(THEMES):
        raise TokenError(f"'themes' must contain exactly {', '.join(THEMES)}")

    common: Declarations = []
    for key, value in tokens.items():
        if key not in SKIPPED_KEYS:
            common.extend(_flatten(value, (key,)))
    light = _flatten(themes["light"], ())
    dark = _flatten(themes["dark"], ())
    if [name for name, _ in light] != [name for name, _ in dark]:
        raise TokenError("the light and dark themes must define the same tokens in the same order")

    blocks = [
        HEADER,
        _block(":root", common),
        _block(':root,\n[data-theme="light"]', light),
        _block('[data-theme="dark"]', dark),
        "@media (prefers-color-scheme: dark) {\n"
        + _block(':root:not([data-theme="light"])', dark, indent="  ")
        + "\n}",
    ]
    return "\n".join(blocks) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate tokens.css from tokens.json.")
    parser.add_argument("--check", action="store_true", help="fail if tokens.css is out of date")
    args = parser.parse_args(argv)

    css = render(json.loads(SOURCE.read_text(encoding="utf-8")))
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != css:
            sys.stderr.write(
                f"{TARGET.relative_to(ROOT)} is out of date: run `uv run just gen` and commit it.\n"
            )
            return 1
        return 0
    TARGET.write_text(css, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
