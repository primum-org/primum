"""What the runtime declares it has claimed, for ``primum-safe``."""

import json
from pathlib import Path

import pytest

from primum_runtime import declared
from primum_runtime.declared import Declaration
from primum_runtime.errors import PrimumError
from primum_runtime.hal import Claim, InputSpec, OutputSpec, Pull, PwmSpec

LED = OutputSpec(pin=17, active_low=True)
DIMMER = PwmSpec(pin=18, frequency_hz=25_000)
BUTTON = InputSpec(pin=22, pull=Pull.UP, active_low=True, debounce_ms=20)
DECLARATION = Declaration("rpi4b", (LED,), (DIMMER,))


def test_what_is_declared_is_read_back_as_it_was(tmp_path: Path) -> None:
    declared.write(tmp_path, DECLARATION)

    assert declared.read(tmp_path) == DECLARATION


def test_a_declaration_names_the_outputs_of_a_claim_and_not_its_inputs() -> None:
    claim = Claim(outputs=[LED], inputs=[BUTTON], pwms=[DIMMER])

    declaration = Declaration.of("rpi4b", claim)

    assert declaration == DECLARATION
    assert declaration.claim().pins() == [17, 18]


def test_nothing_declared_reads_as_nothing(tmp_path: Path) -> None:
    assert declared.read(tmp_path) is None


def test_declaring_again_replaces_what_was_declared_and_leaves_no_other_file(
    tmp_path: Path,
) -> None:
    declared.write(tmp_path, DECLARATION)
    declared.write(tmp_path, Declaration("rpi4b", (OutputSpec(pin=27, active_low=False),)))

    assert declared.read(tmp_path) == Declaration("rpi4b", (OutputSpec(27, active_low=False),))
    assert [path.name for path in tmp_path.iterdir()] == [declared.FILE_NAME]


def test_removing_forgets_it_and_removing_nothing_is_fine(tmp_path: Path) -> None:
    declared.write(tmp_path, DECLARATION)

    declared.remove(tmp_path)
    declared.remove(tmp_path)

    assert declared.read(tmp_path) is None


def test_a_directory_that_cannot_be_written_refuses_the_declaration(tmp_path: Path) -> None:
    missing = tmp_path / "nowhere"

    with pytest.raises(PrimumError) as raised:
        declared.write(missing, DECLARATION)

    assert raised.value.code == "safe.declaration_unwritable"
    assert raised.value.params["path"] == str(missing / declared.FILE_NAME)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "{",
        "[]",
        json.dumps({"version": 2, "board": "rpi4b", "outputs": [], "pwms": []}),
        json.dumps({"version": 1, "board": "rpi4b", "outputs": []}),
        json.dumps({"version": 1, "board": 4, "outputs": [], "pwms": []}),
        json.dumps({"version": 1, "board": "rpi4b", "outputs": [{"pin": "17"}], "pwms": []}),
        json.dumps(
            {"version": 1, "board": "rpi4b", "outputs": [{"pin": 17, "activeLow": 0}], "pwms": []}
        ),
    ],
    ids=["empty", "cut", "a list", "version", "no pwms", "board", "pin", "active low"],
)
def test_a_declaration_that_does_not_say_what_it_should_is_an_error_not_a_guess(
    tmp_path: Path, content: str
) -> None:
    (tmp_path / declared.FILE_NAME).write_text(content)

    with pytest.raises(PrimumError) as raised:
        declared.read(tmp_path)

    assert raised.value.code == "safe.declaration_invalid"
