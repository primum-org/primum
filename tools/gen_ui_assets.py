"""Copy the page's shared assets into the runtime package, so it serves them when installed.

The sources stay where they are (``i18n/`` and ``design/``); the runtime gets byte-identical
copies under ``primum_runtime/ui/generated/``, which are never edited by hand.

    uv run just gen         # copy (and remove copies whose source is gone)
    uv run just gen-check   # fail if a copy is missing, stale or extra (part of `just check`)
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "packages" / "runtime" / "src" / "primum_runtime" / "ui" / "generated"


@dataclass(frozen=True)
class Source:
    """Files matching ``pattern`` under ``directory`` are copied to ``TARGET / into``."""

    directory: Path
    pattern: str
    into: str


SOURCES = (
    Source(ROOT / "i18n", "*.json", "i18n"),
    Source(ROOT / "design" / "tokens", "tokens.css", "."),
    Source(ROOT / "design" / "icons", "*.svg", "icons"),
    Source(ROOT / "design" / "logo", "*.svg", "logo"),
)


def expected(sources: tuple[Source, ...], target: Path) -> dict[Path, bytes]:
    """Every file the target must hold, with its content."""
    files: dict[Path, bytes] = {}
    for source in sources:
        for path in sorted(source.directory.glob(source.pattern)):
            files[(target / source.into / path.name).resolve()] = path.read_bytes()
    return files


def differences(files: dict[Path, bytes], target: Path) -> list[str]:
    """What is missing, stale or extra in ``target``, as paths relative to it."""
    present = {path.resolve() for path in target.rglob("*") if path.is_file()}
    problems = [
        f"missing or stale: {path.relative_to(target.resolve())}"
        for path, content in files.items()
        if path not in present or path.read_bytes() != content
    ]
    problems += [f"extra: {path.relative_to(target.resolve())}" for path in present - set(files)]
    return sorted(problems)


def write(files: dict[Path, bytes], target: Path) -> None:
    for path in {path.resolve() for path in target.rglob("*") if path.is_file()} - set(files):
        path.unlink()
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copy i18n and design assets for the page.")
    parser.add_argument("--check", action="store_true", help="fail if a copy is out of date")
    args = parser.parse_args(argv)

    files = expected(SOURCES, TARGET)
    if args.check:
        problems = differences(files, TARGET)
        for problem in problems:
            sys.stderr.write(f"{TARGET.relative_to(ROOT)}: {problem}\n")
        if problems:
            sys.stderr.write("Run `uv run just gen` and commit the result.\n")
        return 1 if problems else 0
    write(files, TARGET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
