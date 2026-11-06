"""``primum``: the command line.

    primum validate <folder> [--lang en|es] [--json] [--strict]

Exit status: ``0`` valid, ``1`` problems found, ``2`` the command could not run.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from primum_cli.folder import read_folder
from primum_cli.messages import DEFAULT_LANGUAGE, LANGUAGES, Catalog
from primum_core.errors import Issue, Severity
from primum_core.workspace import load_workspace

EXIT_VALID = 0
EXIT_PROBLEMS = 1
EXIT_FAILED = 2
# Catalog keys are written out, so the catalog test can find every key the CLI uses.
SEVERITY_KEYS = {Severity.ERROR: "severity.error", Severity.WARNING: "severity.warning"}


def main(argv: Sequence[str] | None = None, out: TextIO | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    return validate(
        args.folder,
        Catalog.load(args.lang),
        as_json=args.json,
        strict=args.strict,
        out=out or sys.stdout,
    )


def validate(folder: Path, catalog: Catalog, *, as_json: bool, strict: bool, out: TextIO) -> int:
    """Check the project in ``folder`` and write what was found."""
    if not folder.is_dir():
        sys.stderr.write(catalog.text("folder.not_a_folder", path=str(folder)) + "\n")
        return EXIT_FAILED
    try:
        files = read_folder(folder)
    except OSError as error:
        sys.stderr.write(
            catalog.text("folder.unreadable", path=str(folder), detail=str(error)) + "\n"
        )
        return EXIT_FAILED
    issues = load_workspace(files).issues
    errors = sum(issue.severity is Severity.ERROR for issue in issues)
    warnings = len(issues) - errors
    valid = errors == 0 and not (strict and warnings)
    if as_json:
        _write_json(folder, issues, catalog, valid, out)
    else:
        _write_text(folder, issues, catalog, valid, out)
    return EXIT_VALID if valid else EXIT_PROBLEMS


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="primum", description="Primum's command line.")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("validate", help="check a project folder, without hardware")
    command.add_argument("folder", type=Path, help="the project's folder (with project.json)")
    command.add_argument(
        "--lang",
        choices=LANGUAGES,
        default=DEFAULT_LANGUAGE,
        help=f"language of the messages, {DEFAULT_LANGUAGE} by default",
    )
    command.add_argument("--json", action="store_true", help="write the result as JSON")
    command.add_argument("--strict", action="store_true", help="warnings make it fail too")
    return parser


def _write_text(
    folder: Path, issues: Sequence[Issue], catalog: Catalog, valid: bool, out: TextIO
) -> None:
    for issue in issues:
        message, hint = catalog.describe(issue)
        place = ""
        if issue.location is not None:
            place = f"{issue.location.path}"
            if issue.location.pointer:
                place += f" {issue.location.pointer}"
            place += ": "
        out.write(f"{catalog.text(SEVERITY_KEYS[issue.severity])}: {place}{message}\n")
        if hint:
            out.write("  " + catalog.text("hint", hint=hint) + "\n")
    errors = sum(issue.severity is Severity.ERROR for issue in issues)
    if valid:
        out.write(catalog.text("result.valid", path=str(folder)) + "\n")
    else:
        out.write(catalog.text("result.invalid", path=str(folder)) + "\n")
    if issues:
        out.write(catalog.text("summary", errors=errors, warnings=len(issues) - errors) + "\n")


def _write_json(
    folder: Path, issues: Sequence[Issue], catalog: Catalog, valid: bool, out: TextIO
) -> None:
    entries: list[dict[str, object]] = []
    for issue in issues:
        message, hint = catalog.describe(issue)
        location = issue.location
        entries.append(
            {
                "code": issue.code.value,
                "severity": issue.severity.value,
                "params": dict(issue.params),
                "path": str(location.path) if location else None,
                "pointer": location.pointer if location else None,
                "fileId": str(location.file_id) if location and location.file_id else None,
                "message": message,
                "hint": hint,
            }
        )
    json.dump(
        {"project": str(folder), "valid": valid, "issues": entries},
        out,
        indent=2,
        ensure_ascii=False,
    )
    out.write("\n")
