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
from pathlib import Path

import pytest

from primum_runtime.board import load_board
from primum_runtime.errors import PrimumError
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


def test_the_other_gpio_of_the_pwm_channel_is_refused_as_not_routed() -> None:
    # With the pwm-2chan overlay, channel 0 reaches GPIO 18 and GPIO 12 stays free: a PWM output
    # on 12 would come out of 18. Nothing is driven: the claim must fail before any request.
    from primum_runtime.hal.gpiod_hal import GpiodHal

    board = load_board("rpi4b")
    routed = _optional_pin(PWM_VARIABLE)
    channel = board.pwm_channels[routed]
    (other,) = [pin for pin, ch in board.pwm_channels.items() if ch == channel and pin != routed]

    with GpiodHal(board) as hal, pytest.raises(PrimumError) as raised:
        hal.claim(Claim(pwms=(PwmSpec(pin=other),)))

    assert raised.value.code == "hal.pwm_not_routed"
    assert raised.value.params == {"pin": other, "channel": channel}


def _polarity_kept_after_unexport(chip: Path, channel: int) -> str:
    """The polarity an unexported channel kept: it shows when the channel is exported again."""
    (chip / "export").write_text(f"{channel}\n")
    try:
        return (chip / f"pwm{channel}" / "polarity").read_text().strip()
    finally:
        (chip / "unexport").write_text(f"{channel}\n")


def test_the_safe_state_and_the_release_put_an_inverted_polarity_back() -> None:
    # What test_hal_pwm.py assumes of the kernel, checked on the real one: a polarity inverted
    # while the HAL runs (accepted on an enabled channel) holds the pin high at 0 %, and both
    # the safe state and the release put it back. An LED on the pin flashes twice.
    from primum_runtime.hal.gpiod_hal import GpiodHal
    from primum_runtime.hal.pwm_sysfs import find_pwm_chip

    board = load_board("rpi4b")
    pin = _optional_pin(PWM_VARIABLE)
    channel = board.pwm_channels[pin]
    chip = find_pwm_chip(board.pwm_device)
    polarity = chip / f"pwm{channel}" / "polarity"

    with GpiodHal(board) as hal:
        hal.claim(Claim(pwms=(PwmSpec(pin=pin, frequency_hz=1000),)))
        pwm = hal.pwms[pin]
        polarity.write_text("inversed\n")
        assert pwm.read() == 1.0

        hal.apply_safe_state()

        assert polarity.read_text().strip() == "normal"
        assert pwm.read() == 0.0
        polarity.write_text("inversed\n")  # once more, for the release on leaving the block

    assert _polarity_kept_after_unexport(chip, channel) == "normal"
