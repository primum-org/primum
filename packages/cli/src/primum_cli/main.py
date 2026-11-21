"""``primum``: the command line.

    primum validate <folder> [--lang en|es] [--json] [--strict]
    primum build <folder> [--output <file>] [--lang en|es]

``build`` compiles the project into its deployment package, ``<folder>.package.json`` in the
current folder unless ``--output`` says where.

Exit status: ``0`` valid (or built), ``1`` problems found, ``2`` the command could not run.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import TextIO

from primum_cli.boards import load_profiles
from primum_cli.drivers import load_drivers
from primum_cli.folder import read_folder
from primum_cli.messages import DEFAULT_LANGUAGE, LANGUAGES, Catalog
from primum_core.compiler import compile_package
from primum_core.errors import Issue, Severity
from primum_core.workspace import load_workspace

EXIT_VALID = 0
EXIT_PROBLEMS = 1
EXIT_FAILED = 2
# Catalog keys are written out, so the catalog test can find every key the CLI uses.
SEVERITY_KEYS = {Severity.ERROR: "severity.error", Severity.WARNING: "severity.warning"}


def main(
    argv: Sequence[str] | None = None, out: TextIO | None = None, err: TextIO | None = None
) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    catalog = Catalog.load(args.lang)
    to, errors = out or sys.stdout, err or sys.stderr
    if args.command == "build":
        output = args.output or Path(f"{args.folder.resolve().name}.package.json")
        return build(args.folder, output, catalog, out=to, err=errors)
    return validate(args.folder, catalog, as_json=args.json, strict=args.strict, out=to, err=errors)


def validate(
    folder: Path, catalog: Catalog, *, as_json: bool, strict: bool, out: TextIO, err: TextIO
) -> int:
    """Check the project in ``folder``: what was found goes to ``out``, why it could not run to
    ``err``."""
    files = _read(folder, catalog, err)
    if files is None:
        return EXIT_FAILED
    issues = load_workspace(files, load_profiles(), load_drivers()).issues
    errors = sum(issue.severity is Severity.ERROR for issue in issues)
    warnings = len(issues) - errors
    valid = errors == 0 and not (strict and warnings)
    if as_json:
        _write_json(folder, issues, catalog, valid, out)
    else:
        _write_text(folder, issues, catalog, valid, out)
    return EXIT_VALID if valid else EXIT_PROBLEMS


def build(folder: Path, output: Path, catalog: Catalog, *, out: TextIO, err: TextIO) -> int:
    """Compile the project in ``folder`` into its deployment package, written to ``output``.
    A project with errors is not built; warnings are shown and it is built all the same."""
    files = _read(folder, catalog, err)
    if files is None:
        return EXIT_FAILED
    drivers = load_drivers()
    loaded = load_workspace(files, load_profiles(), drivers)
    issues = list(loaded.issues)
    package = None
    if loaded.value is not None:
        compiled = compile_package(loaded.value, drivers)
        issues += compiled.issues
        package = compiled.value
    _write_text(folder, issues, catalog, package is not None, out)
    if package is None:
        return EXIT_PROBLEMS
    text = json.dumps(package, indent=2, ensure_ascii=False) + "\n"
    try:
        output.write_text(text, encoding="utf-8")
    except OSError as error:
        err.write(catalog.text("build.unwritable", path=str(output), detail=str(error)) + "\n")
        return EXIT_FAILED
    out.write(catalog.text("build.written", path=str(output), hash=str(package["hash"])) + "\n")
    return EXIT_VALID


def _read(folder: Path, catalog: Catalog, err: TextIO) -> dict[PurePosixPath, bytes] | None:
    """The files of the project folder, or ``None`` with the reason written to ``err``."""
    if not folder.is_dir():
        err.write(catalog.text("folder.not_a_folder", path=str(folder)) + "\n")
        return None
    try:
        return read_folder(folder)
    except OSError as error:
        err.write(catalog.text("folder.unreadable", path=str(folder), detail=str(error)) + "\n")
        return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="primum", description="Primum's command line.")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("validate", help="check a project folder, without hardware")
    _common_arguments(command)
    command.add_argument("--json", action="store_true", help="write the result as JSON")
    command.add_argument("--strict", action="store_true", help="warnings make it fail too")
    command = commands.add_parser("build", help="compile a project into its deployment package")
    _common_arguments(command)
    command.add_argument("--output", type=Path, help="where to write the package")
    return parser


def _common_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("folder", type=Path, help="the project's folder (with project.json)")
    command.add_argument(
        "--lang",
        choices=LANGUAGES,
        default=DEFAULT_LANGUAGE,
        help=f"language of the messages, {DEFAULT_LANGUAGE} by default",
    )


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
