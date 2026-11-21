"""``primum build``: the deployment package it writes, and when it writes none."""

import json
import shutil
from io import StringIO
from pathlib import Path, PurePosixPath

import pytest

from primum_cli.main import EXIT_FAILED, EXIT_PROBLEMS, EXIT_VALID, main
from primum_core.package import read_package

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "examples"


def _build(*args: str) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    status = main(["build", *args], out, err)
    return status, out.getvalue(), err.getvalue()


@pytest.mark.parametrize(
    "example",
    sorted(p for p in EXAMPLES.iterdir() if p.is_dir() and p.name != "invalid"),
    ids=lambda p: p.name,
)
def test_every_example_builds_into_a_package_that_reads_back(example: Path, tmp_path: Path) -> None:
    output = tmp_path / "out.package.json"

    status, out, _ = _build(str(example), "--output", str(output))

    assert status == EXIT_VALID, out
    read = read_package(PurePosixPath(output.name), output.read_bytes())
    assert read.value is not None, read.issues
    assert read.value.hash in out
    assert str(output) in out


def test_without_an_output_the_package_is_named_after_the_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    status, _, _ = _build(str(EXAMPLES / "minimal"))

    assert status == EXIT_VALID
    assert json.loads((tmp_path / "minimal.package.json").read_text())["kind"] == "package"


def test_a_project_with_errors_is_not_built(tmp_path: Path) -> None:
    output = tmp_path / "out.package.json"

    status, out, _ = _build(str(EXAMPLES / "invalid" / "pin-in-use"), "--output", str(output))

    assert status == EXIT_PROBLEMS
    assert "error:" in out
    assert not output.exists()


def test_a_project_on_several_boards_says_why_it_is_not_built(tmp_path: Path) -> None:
    folder = tmp_path / "project"
    shutil.copytree(EXAMPLES / "minimal", folder)
    board = {"id": "9d1c3f0e-5a1b-4c58-9e57-0a6f3f3f6a01", "name": "Second Pi", "model": "rpi4b"}
    other = {"id": "9d1c3f0e-5a1b-4c58-9e57-0a6f3f3f6a02", "kind": "hardware", "schemaVersion": 1}
    (folder / "other.hw").write_text(json.dumps({**other, "boards": [board], "elements": []}))
    output = tmp_path / "out.package.json"

    status, out, _ = _build(str(folder), "--output", str(output), "--lang", "es")

    assert status == EXIT_PROBLEMS
    assert "varias placas" in out
    assert "Second Pi" in out
    assert not output.exists()


def test_a_package_that_cannot_be_written_fails_with_the_reason(tmp_path: Path) -> None:
    output = tmp_path / "missing" / "out.package.json"

    status, _, err = _build(str(EXAMPLES / "minimal"), "--output", str(output))

    assert status == EXIT_FAILED
    assert str(output) in err


def test_a_folder_that_is_not_one_fails(tmp_path: Path) -> None:
    status, _, err = _build(str(tmp_path / "nothing"))

    assert status == EXIT_FAILED
    assert "nothing" in err


def test_building_from_inside_the_project_does_not_make_the_package_part_of_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "project"
    shutil.copytree(EXAMPLES / "minimal", folder)
    monkeypatch.chdir(folder)
    first = _build(".")

    again = _build(".")
    out = StringIO()
    validated = main(["validate", ".", "--strict"], out, StringIO())

    assert (folder / "project.package.json").exists()
    assert (first[0], again[0], validated) == (EXIT_VALID, EXIT_VALID, EXIT_VALID), out.getvalue()
    assert "warning" not in again[1]
