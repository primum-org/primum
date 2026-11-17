"""The drivers on a real board: they run only on the Pi (`just test-hw`).

The same pins and the same care as `test_hal_gpiod_hw.py`: PRIMUM_HW_TEST_PIN (required),
PRIMUM_HW_INPUT_PIN and PRIMUM_HW_PWM_PIN (optional), each with nothing wired to it, or only an
LED (a button to ground on the input, not pressed, is fine). Never a relay or a motor driver,
and never on a Pi where other software drives GPIO.

They check what the limits of the board profile and of the manifests say on the board itself:
both ends of the PWM frequency and the longest debounce, which until here were arithmetic on
the documentation. And an input sees a real edge without a finger: changing its pull from up
to down flips a line that nothing drives.
"""

import os
import time
from datetime import timedelta

import pytest

from primum_runtime.board import load_board, load_profile, option_limits
from primum_runtime.drivers import (
    DigitalInputDriver,
    ElementConfig,
    OutputDriver,
    create_driver,
    load_manifests,
)
from primum_runtime.hal import Claim, Hal, InputSpec, OutputSpec, PwmSpec

pytestmark = pytest.mark.hw

PIN_VARIABLE = "PRIMUM_HW_TEST_PIN"
INPUT_VARIABLE = "PRIMUM_HW_INPUT_PIN"
PWM_VARIABLE = "PRIMUM_HW_PWM_PIN"
BOARD = "rpi4b"
MANIFESTS = load_manifests()
LIMITS = option_limits(load_profile(BOARD))
LOWEST_HZ, HIGHEST_HZ = (int(limit) for limit in LIMITS["pwm_output", "frequencyHz"])
LONGEST_DEBOUNCE_MS = 10_000


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


def _open() -> Hal:
    from primum_runtime.hal.gpiod_hal import GpiodHal

    return GpiodHal(load_board(BOARD))


def _claim(hal: Hal, element: ElementConfig) -> OutputDriver | DigitalInputDriver:
    driver = create_driver(element, MANIFESTS, LIMITS)
    assert isinstance(driver, OutputDriver | DigitalInputDriver)
    spec = driver.spec
    hal.claim(
        Claim(
            outputs=[spec] if isinstance(spec, OutputSpec) else [],
            inputs=[spec] if isinstance(spec, InputSpec) else [],
            pwms=[spec] if isinstance(spec, PwmSpec) else [],
        )
    )
    driver.bind(hal)
    return driver


def _set_pull(hal: Hal, driver: DigitalInputDriver, pull_up: bool) -> None:
    """Change the pull of a claimed input, keeping the rest of its settings: on a line that
    nothing drives, the level follows the pull, which is a real edge."""
    import gpiod
    from gpiod.line import Bias, Direction, Edge

    from primum_runtime.hal.gpiod_hal import GpiodHal

    assert isinstance(hal, GpiodHal)
    spec = driver.spec
    settings = gpiod.LineSettings(
        direction=Direction.INPUT,
        edge_detection=Edge.BOTH,
        bias=Bias.PULL_UP if pull_up else Bias.PULL_DOWN,
        active_low=spec.active_low,
        debounce_period=timedelta(milliseconds=spec.debounce_ms),
    )
    # The HAL has no way to reconfigure a line, and needs none outside this test.
    request = hal._request  # pyright: ignore[reportPrivateUsage]
    assert request is not None
    request.reconfigure_lines({hal.board.line(spec.pin): settings})


def _button(pin: int, debounce_ms: int) -> ElementConfig:
    options = {"pull": "up", "debounceMs": debounce_ms}
    return ElementConfig("button", "digital_input", pin, active_low=True, options=options)


def test_a_digital_output_reads_back_what_its_driver_commands() -> None:
    led = ElementConfig("led", "digital_output", _pin(PIN_VARIABLE), active_low=False)
    with _open() as hal:
        driver = _claim(hal, led)
        assert isinstance(driver, OutputDriver)

        driver.command("on")  # raises if the line does not read back on
        assert driver.level == 100

        driver.command("off")  # the safe state of its manifest
        assert driver.level == 0


@pytest.mark.parametrize("frequency_hz", [LOWEST_HZ, HIGHEST_HZ])
def test_a_pwm_output_works_at_both_ends_of_what_the_profile_says(frequency_hz: int) -> None:
    options = {"frequencyHz": frequency_hz}
    dimmer = ElementConfig("dimmer", "pwm_output", _optional_pin(PWM_VARIABLE), False, options)
    with _open() as hal:
        driver = _claim(hal, dimmer)
        assert isinstance(driver, OutputDriver)

        # Each raises if the level read back is further than one step from the one written.
        driver.command("set", {"level": 50})
        driver.command("set", {"level": 100 / 3})
        driver.command("on")
        driver.command("off")  # the safe state of its manifest

        assert hal.pwms[dimmer.pin].read() == 0.0


def test_an_input_sees_a_real_edge_with_its_polarity_its_time_and_its_number() -> None:
    with _open() as hal:
        driver = _claim(hal, _button(_optional_pin(INPUT_VARIABLE), debounce_ms=0))
        assert isinstance(driver, DigitalInputDriver)
        assert not driver.active  # pulled up, and active low
        before_ns = time.monotonic_ns()

        _set_pull(hal, driver, pull_up=False)  # the line falls: active
        assert hal.wait_events(1.0)
        pressed = hal.read_events()
        _set_pull(hal, driver, pull_up=True)  # and rises again
        assert hal.wait_events(1.0)
        released = hal.read_events()

        for event in (*pressed, *released):
            driver.handle(event)
        assert [event.active for event in (*pressed, *released)] == [True, False]
        assert [event.sequence for event in (*pressed, *released)] == [1, 2]
        assert before_ns <= pressed[0].timestamp_ns <= released[0].timestamp_ns
        assert released[0].timestamp_ns <= time.monotonic_ns()
        assert not driver.active
        assert driver.lost_events == 0


def test_an_input_takes_the_longest_debounce_and_holds_an_edge_back_that_long() -> None:
    """Slow on purpose: it waits the ten seconds the manifest allows."""
    with _open() as hal:
        button = _button(_optional_pin(INPUT_VARIABLE), debounce_ms=LONGEST_DEBOUNCE_MS)
        driver = _claim(hal, button)
        assert isinstance(driver, DigitalInputDriver)

        _set_pull(hal, driver, pull_up=False)

        assert not hal.wait_events(1.0)  # still within the debounce time
        assert hal.wait_events(LONGEST_DEBOUNCE_MS / 1000 + 2)
        (event,) = hal.read_events()
        assert event.active
