"""Real GPIO tests: they run only on the Pi (`just test-hw`).

They drive a real line, so the pin is never assumed: set PRIMUM_HW_TEST_PIN to a GPIO with
nothing wired to it, or only an LED. Never a pin with a relay or a motor driver, and never on a
Pi where other software drives GPIO (it may own lines the kernel reports as free).

They check what the kernel reports for the line, not that an LED lights up: that is checked
by eye in block 1.4.
"""

import os

import pytest

from primum_runtime.hal import OutputSpec

pytestmark = pytest.mark.hw

PIN_VARIABLE = "PRIMUM_HW_TEST_PIN"


def _test_pin() -> int:
    value = os.environ.get(PIN_VARIABLE)
    if value is None:
        # A failure, not a skip: `just test-hw` must never pass without driving a line.
        pytest.fail(f"set {PIN_VARIABLE} to a GPIO with nothing wired to it, or only an LED")
    return int(value)


def test_gpiod_line_starts_inactive_and_the_kernel_reports_each_written_value() -> None:
    from primum_runtime.hal.gpiod_hal import GpiodHal

    pin = _test_pin()
    with GpiodHal() as hal:
        output = hal.digital_output(OutputSpec(pin=pin))
        assert not output.read()

        output.set(True)
        assert output.read()

        output.set(False)
        assert not output.read()
