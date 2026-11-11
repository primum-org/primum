"""Copy shared files into the packages that ship them, so they have them once installed.

The sources stay where they are; the packages get byte-identical copies, never edited by hand:

- runtime: the page's assets (``i18n/``, ``design/``) under ``primum_runtime/ui/generated/``,
  and the board profiles (``boards/``) under ``primum_runtime/generated/boards/``;
- CLI: the message catalogs (``i18n/``) under ``primum_cli/generated/i18n/``, the board
  profiles under ``primum_cli/generated/boards/`` and the driver manifests (``drivers/``) under
  ``primum_cli/generated/drivers/``.

    uv run just gen         # copy (and remove copies whose source is gone)
    uv run just gen-check   # fail if a copy is missing, stale or extra (part of `just check`)
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "packages" / "runtime" / "src" / "primum_runtime"
CLI = ROOT / "packages" / "cli" / "src" / "primum_cli"


@dataclass(frozen=True)
class Source:
    """Files matching ``pattern`` under ``directory`` are copied to ``TARGET / into``."""

    directory: Path
    pattern: str
    into: str


# Each target directory, with what it holds. A target holds nothing else: extra files go.
TARGETS: dict[Path, tuple[Source, ...]] = {
    RUNTIME / "ui" / "generated": (
        Source(ROOT / "i18n", "*.json", "i18n"),
        Source(ROOT / "design" / "tokens", "tokens.css", "."),
        Source(ROOT / "design" / "icons", "*.svg", "icons"),
        Source(ROOT / "design" / "logo", "*.svg", "logo"),
    ),
    RUNTIME / "generated" / "boards": (Source(ROOT / "boards", "*.json", "."),),
    CLI / "generated" / "i18n": (Source(ROOT / "i18n", "*.json", "."),),
    CLI / "generated" / "boards": (Source(ROOT / "boards", "*.json", "."),),
    CLI / "generated" / "drivers": (Source(ROOT / "drivers", "*.json", "."),),
}


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
    parser = argparse.ArgumentParser(description="Copy shared files into the packages.")
    parser.add_argument("--check", action="store_true", help="fail if a copy is out of date")
    args = parser.parse_args(argv)

    stale = False
    for target, sources in TARGETS.items():
        files = expected(sources, target)
        if not args.check:
            write(files, target)
            continue
        for problem in differences(files, target):
            stale = True
            sys.stderr.write(f"{target.relative_to(ROOT)}: {problem}\n")
    if stale:
        sys.stderr.write("Run `uv run just gen` and commit the result.\n")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
