"""Real GPIO tests: they run only on the Pi (`just test-hw`).

They drive real lines, so no pin is ever assumed:
- PRIMUM_HW_TEST_PIN (required): a GPIO with nothing wired to it, or only an LED;
- PRIMUM_HW_INPUT_PIN (optional): a GPIO with a button to ground, or nothing (the pull-up
  reads as not pressed);
- PRIMUM_HW_PWM_PIN (optional): a GPIO with hardware PWM (12, 13, 18 or 19) with nothing wired,
  or only an LED, once the pwm overlay is enabled.
Never a pin with a relay or a motor driver, and never on a Pi where other software drives GPIO
(it may own lines the kernel reports as free).

They check what the kernel reports for the lines, not that an LED lights up: that is checked
by eye.
"""

import os

import pytest

from primum_runtime.board import load_board
from primum_runtime.hal import Claim, InputSpec, OutputSpec, Pull, PwmSpec

pytestmark = pytest.mark.hw

PIN_VARIABLE = "PRIMUM_HW_TEST_PIN"
INPUT_VARIABLE = "PRIMUM_HW_INPUT_PIN"
PWM_VARIABLE = "PRIMUM_HW_PWM_PIN"


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


def test_gpiod_line_starts_inactive_and_the_kernel_reports_each_written_value() -> None:
    from primum_runtime.hal.gpiod_hal import GpiodHal

    with GpiodHal(load_board("rpi4b")) as hal:
        hal.claim(Claim(outputs=(OutputSpec(pin=_pin(PIN_VARIABLE)),)))
        (output,) = hal.outputs.values()
        assert not output.read()

        output.set(True)
        assert output.read()

        output.set(False)
        assert not output.read()


def test_an_input_with_a_pull_up_reads_as_not_pressed_and_has_no_pending_events() -> None:
    from primum_runtime.hal.gpiod_hal import GpiodHal

    with GpiodHal(load_board("rpi4b")) as hal:
        hal.claim(
            Claim(
                inputs=(
                    InputSpec(pin=_optional_pin(INPUT_VARIABLE), pull=Pull.UP, active_low=True),
                )
            )
        )
        (button,) = hal.inputs.values()

        assert not button.read()
        assert not hal.wait_events(0.2)
        assert hal.read_events() == []


def test_a_pwm_output_starts_at_zero_and_reads_back_what_is_set() -> None:
    from primum_runtime.hal.gpiod_hal import GpiodHal

    with GpiodHal(load_board("rpi4b")) as hal:
        hal.claim(Claim(pwms=(PwmSpec(pin=_optional_pin(PWM_VARIABLE), frequency_hz=1000),)))
        (pwm,) = hal.pwms.values()
        assert pwm.read() == 0.0

        pwm.set(0.5)
        assert pwm.read() == 0.5

        pwm.set(0.0)
        assert pwm.read() == 0.0
