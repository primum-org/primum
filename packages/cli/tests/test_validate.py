"""``primum validate``: what it writes, in which language, and how it exits."""

import json
import shutil
from io import StringIO
from pathlib import Path

import pytest

from primum_cli.main import EXIT_FAILED, EXIT_PROBLEMS, EXIT_VALID, main

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "examples"
MINIMAL = EXAMPLES / "minimal"


def _run(*args: str, err: StringIO | None = None) -> tuple[int, str]:
    out = StringIO()
    status = main(["validate", *args], out, err or StringIO())
    return status, out.getvalue()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A copy of the minimal example, to break."""
    folder = tmp_path / "project"
    shutil.copytree(MINIMAL, folder)
    return folder


INVALID = EXAMPLES / "invalid"
# Each invalid example gives exactly the code it is named after.
INVALID_CODES = {
    "board-unknown-model": "board.unknown_model",
    "pin-not-on-board": "pin.not_on_board",
    "pin-reserved": "pin.reserved",
    "pin-in-use": "pin.in_use",
    "pin-claimed-by-bus": "pin.claimed_by_bus",
    "pin-function-unavailable": "pin.function_unavailable",
    "pwm-channel-in-use": "pwm.channel_in_use",
    "bus-not-on-board": "bus.not_on_board",
    "bus-not-i2c": "bus.not_i2c",
    "i2c-address-in-use": "i2c.address_in_use",
    "action-unknown": "action.unknown",
    "action-param-missing": "action.param_missing",
    "action-param-out-of-range": "action.param_out_of_range",
    "track-element-without-actions": "track.element_without_actions",
    "config-out-of-range": "config.out_of_range",
    "config-not-allowed": "config.not_allowed",
}


@pytest.mark.parametrize(
    "example",
    sorted(p for p in EXAMPLES.iterdir() if p.is_dir() and p != INVALID),
    ids=lambda p: p.name,
)
def test_every_example_is_valid(example: Path) -> None:
    status, out = _run(str(example), "--strict")

    assert status == EXIT_VALID, out


def test_the_invalid_examples_are_exactly_the_ones_the_test_knows() -> None:
    assert {p.name for p in INVALID.iterdir() if p.is_dir()} == set(INVALID_CODES)


@pytest.mark.parametrize(("example", "code"), sorted(INVALID_CODES.items()))
def test_each_invalid_example_gives_exactly_its_code(example: str, code: str) -> None:
    status, out = _run(str(INVALID / example), "--json")

    assert status == EXIT_PROBLEMS
    assert [issue["code"] for issue in json.loads(out)["issues"]] == [code]


def test_a_valid_project_says_so_and_exits_0() -> None:
    status, out = _run(str(MINIMAL))

    assert status == EXIT_VALID
    assert out == f"{MINIMAL}: the project is valid.\n"


def test_each_problem_is_written_with_its_place_message_and_hint(project: Path) -> None:
    hardware = json.loads((project / "hardware.hw").read_text(encoding="utf-8"))
    del hardware["elements"][0]["pin"]
    (project / "hardware.hw").write_text(json.dumps(hardware), encoding="utf-8")

    status, out = _run(str(project))

    assert status == EXIT_PROBLEMS
    assert out.splitlines() == [
        "error: hardware.hw /elements/0: The field elements[0].pin is missing.",
        "  Hint: Add it: this format requires it.",
        f"{project}: the project has problems.",
        "Errors: 1. Warnings: 0.",
    ]


def test_messages_come_in_spanish_with_lang_es(project: Path) -> None:
    (project / "blink.sec").write_text("{", encoding="utf-8")

    status, out = _run(str(project), "--lang", "es")

    assert status == EXIT_PROBLEMS
    assert out.splitlines()[0] == (
        "error: blink.sec: El fichero no es JSON válido (línea 1, columna 2)."
    )
    assert out.splitlines()[-1] == "Errores: 1. Avisos: 0."


def test_lists_are_joined_for_the_language(project: Path) -> None:
    hardware = json.loads((project / "hardware.hw").read_text(encoding="utf-8"))
    hardware["kind"] = "sequence"
    (project / "hardware.hw").write_text(json.dumps(hardware), encoding="utf-8")

    _, out = _run(str(project), "--lang", "es")

    assert "Usa uno de estos: hardware." in out


def test_warnings_pass_unless_strict(project: Path) -> None:
    (project / "notes.txt").write_text("to do", encoding="utf-8")

    assert _run(str(project))[0] == EXIT_VALID
    assert _run(str(project), "--strict")[0] == EXIT_PROBLEMS


def test_hidden_files_are_not_part_of_the_project(project: Path) -> None:
    (project / ".git").mkdir()
    (project / ".git" / "config").write_text("[core]", encoding="utf-8")

    assert _run(str(project), "--strict") == (EXIT_VALID, f"{project}: the project is valid.\n")


def test_json_gives_codes_params_places_and_the_text_in_english_by_default(project: Path) -> None:
    (project / "project.json").unlink()

    status, out = _run(str(project), "--json")

    assert status == EXIT_PROBLEMS
    assert json.loads(out) == {
        "project": str(project),
        "valid": False,
        "issues": [
            {
                "code": "project.manifest_missing",
                "severity": "error",
                "params": {},
                "path": "project.json",
                "pointer": "",
                "fileId": None,
                "message": "The folder has no project.json, so it is not a Primum project.",
                "hint": "Open the project's folder, or create the project from Primum.",
            }
        ],
    }


def test_a_path_that_is_not_a_folder_exits_2_saying_so_on_err(tmp_path: Path) -> None:
    err = StringIO()

    status, out = _run(str(tmp_path / "missing"), err=err)

    assert (status, out) == (EXIT_FAILED, "")
    assert err.getvalue() == f"{tmp_path / 'missing'} is not a folder.\n"


def test_a_wrong_option_exits_2() -> None:
    with pytest.raises(SystemExit) as raised:
        _run(str(MINIMAL), "--lang", "fr")

    assert raised.value.code == EXIT_FAILED
