"""``primum-safe`` on a real board: they run only on the Pi (`just test-hw`).

What block 3.4 is done by: a process that claimed outputs and was killed at once (``SIGKILL``)
leaves them as they were, and ``primum-safe`` puts them in their safe state from what that
process had declared. The same pins and the same care as ``test_hal_gpiod_hw.py``:
PRIMUM_HW_TEST_PIN (required) and PRIMUM_HW_PWM_PIN (optional), each with nothing wired to it,
or only an LED. Never a relay or a motor driver, and never on a Pi where other software drives
GPIO.

An LED on the pin is the witness: it goes on, stays on after the kill, and goes off.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from primum_runtime import declared
from primum_runtime.board import load_board
from primum_runtime.hal import Hal
from primum_runtime.safe import EXIT_SAFE, make_safe

pytestmark = pytest.mark.hw

PIN_VARIABLE = "PRIMUM_HW_TEST_PIN"
PWM_VARIABLE = "PRIMUM_HW_PWM_PIN"
BOARD = "rpi4b"
TIMEOUT_S = 20

# A stand-in for the service: it declares what it claims, turns it on and is killed at once,
# so nothing of its own can put the output back.
KILLED_WITH_AN_OUTPUT_ON = """
import os, signal, sys
from pathlib import Path
from primum_runtime import declared
from primum_runtime.board import load_board
from primum_runtime.hal import Claim, OutputSpec, PwmSpec
from primum_runtime.hal.gpiod_hal import GpiodHal

kind, pin, directory = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
if kind == "output":
    claim = Claim(outputs=[OutputSpec(pin=pin, active_low=False)])
else:
    claim = Claim(pwms=[PwmSpec(pin=pin, frequency_hz=1000)])
hal = GpiodHal(load_board("rpi4b"))
declared.write(directory, declared.Declaration.of("rpi4b", claim))
hal.claim(claim)
if kind == "output":
    hal.outputs[pin].set(True)
else:
    hal.pwms[pin].set(0.5)
os.kill(os.getpid(), signal.SIGKILL)
"""


def _pin(variable: str) -> int:
    value = os.environ.get(variable)
    if value is None:
        # A failure, not a skip: `just test-hw` must never pass without driving a line.
        pytest.fail(f"set {variable} to a GPIO with nothing wired to it, or only an LED")
    if not value.isdecimal():
        pytest.fail(f"{variable} must be a GPIO number, not {value!r}")
    return int(value)


def _optional_pin(variable: str) -> int:
    if variable not in os.environ:
        pytest.skip(f"{variable} not set")
    return _pin(variable)


def _open(model: str) -> Hal:
    from primum_runtime.hal.gpiod_hal import GpiodHal

    return GpiodHal(load_board(model))


def _kill_with_an_output_on(kind: str, pin: int, directory: Path) -> None:
    command = [sys.executable, "-c", KILLED_WITH_AN_OUTPUT_ON, kind, str(pin), str(directory)]
    result = subprocess.run(  # noqa: S603 (this interpreter, a script of this file)
        command, capture_output=True, text=True, timeout=TIMEOUT_S, check=False
    )
    assert result.returncode == -signal.SIGKILL, result.stderr


def _line_is_high(pin: int) -> bool:
    """The level of a line nobody holds, read without changing how it is driven."""
    import gpiod
    from gpiod.line import Direction, Value

    from primum_runtime.hal.gpiod_hal import GpiodHal

    with GpiodHal(load_board(BOARD)) as hal:
        line = hal.board.line(pin)
        chip = hal._chip  # pyright: ignore[reportPrivateUsage]  # the HAL never reads a line it has not claimed
        settings = gpiod.LineSettings(direction=Direction.AS_IS)
        with chip.request_lines({line: settings}, consumer="primum-test") as request:
            return request.get_value(line) == Value.ACTIVE


def test_a_digital_output_left_on_by_a_killed_process_is_turned_off(tmp_path: Path) -> None:
    pin = _pin(PIN_VARIABLE)

    _kill_with_an_output_on("output", pin, tmp_path)
    assert _line_is_high(pin)  # the kernel kept it as the dead process left it

    assert make_safe(tmp_path, _open) == EXIT_SAFE
    assert not _line_is_high(pin)
    assert declared.read(tmp_path) is None


def test_a_pwm_output_left_running_by_a_killed_process_is_stopped(tmp_path: Path) -> None:
    from primum_runtime.hal.pwm_sysfs import find_pwm_chip

    board = load_board(BOARD)
    pin = _optional_pin(PWM_VARIABLE)
    channel = find_pwm_chip(board.pwm_device) / f"pwm{board.pwm_channels[pin]}"

    _kill_with_an_output_on("pwm", pin, tmp_path)
    assert (channel / "enable").read_text().strip() == "1"  # still running at 50 %
    assert int((channel / "duty_cycle").read_text()) > 0

    assert make_safe(tmp_path, _open) == EXIT_SAFE
    assert not channel.exists()  # at 0 %, disabled and unexported
    assert declared.read(tmp_path) is None
