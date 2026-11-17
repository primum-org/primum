"""``primum-safe``: what the dead service declared goes to its safe state."""

from pathlib import Path

import pytest

from primum_runtime import declared
from primum_runtime.board import load_board
from primum_runtime.declared import Declaration
from primum_runtime.hal import Claim, OutputSpec, PwmSpec, SimulatedHal
from primum_runtime.hal.base import Drivers
from primum_runtime.safe import EXIT_FAILED, EXIT_SAFE, make_safe

LED = OutputSpec(pin=17, active_low=False)
DIMMER = PwmSpec(pin=18, frequency_hz=1000)
DECLARATION = Declaration("rpi4b", (LED,), (DIMMER,))


class Boards:
    """Hands out one simulated HAL per call, and remembers them and the models asked for."""

    def __init__(self) -> None:
        self.hals: list[SimulatedHal] = []
        self.models: list[str] = []

    def open(self, model: str) -> SimulatedHal:
        self.models.append(model)
        self.hals.append(SimulatedHal(load_board(model)))
        return self.hals[-1]


@pytest.fixture
def boards() -> Boards:
    return Boards()


def test_with_nothing_declared_nothing_is_touched(tmp_path: Path, boards: Boards) -> None:
    assert make_safe(tmp_path, boards.open) == EXIT_SAFE
    assert boards.hals == []


def test_what_was_declared_is_claimed_made_safe_released_and_forgotten(
    tmp_path: Path, boards: Boards
) -> None:
    declared.write(tmp_path, DECLARATION)

    status = make_safe(tmp_path, boards.open)

    (hal,) = boards.hals
    assert status == EXIT_SAFE
    assert boards.models == ["rpi4b"]
    assert not hal.lines[17].active
    assert hal.lines[17].released
    assert hal.pwm_lines[18].duty == 0.0
    assert hal.pwm_lines[18].released
    assert declared.read(tmp_path) is None


class StuckOn(SimulatedHal):
    """A board whose output lines read back on whatever is written."""

    def _claim(self, claim: Claim) -> Drivers:
        drivers = super()._claim(claim)
        for line in self.lines.values():
            line.stick(True)
        return drivers


def test_an_output_that_does_not_read_back_safe_fails_and_stays_declared(tmp_path: Path) -> None:
    declared.write(tmp_path, DECLARATION)

    status = make_safe(tmp_path, lambda model: StuckOn(load_board(model)))

    assert status == EXIT_FAILED
    assert declared.read(tmp_path) == DECLARATION


def test_a_declaration_that_cannot_be_read_fails_without_touching_anything(
    tmp_path: Path, boards: Boards, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / declared.FILE_NAME).write_text("{")

    assert make_safe(tmp_path, boards.open) == EXIT_FAILED
    assert boards.hals == []
    assert "safe.declaration_invalid" in caplog.text


def test_a_pin_the_board_does_not_have_fails_and_stays_declared(
    tmp_path: Path, boards: Boards
) -> None:
    wrong = Declaration("rpi4b", (OutputSpec(pin=99, active_low=False),))
    declared.write(tmp_path, wrong)

    assert make_safe(tmp_path, boards.open) == EXIT_FAILED
    assert declared.read(tmp_path) == wrong
