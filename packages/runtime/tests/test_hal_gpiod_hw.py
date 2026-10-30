"""Real GPIO tests: they run only on the Pi (`just test-hw`).

They check what the kernel reports for the line, not that an LED lights up: that is checked
by eye in block 1.4. The pin defaults to GPIO 17 and can be changed with PRIMUM_HW_TEST_PIN.
"""

import os

import pytest

from primum_runtime.hal import OutputSpec

pytestmark = pytest.mark.hw

PIN = int(os.environ.get("PRIMUM_HW_TEST_PIN", "17"))


def test_gpiod_line_starts_inactive_and_the_kernel_reports_each_written_value() -> None:
    from primum_runtime.hal.gpiod_hal import GpiodHal

    with GpiodHal() as hal:
        output = hal.digital_output(OutputSpec(pin=PIN))
        assert not output.read()

        output.set(True)
        assert output.read()

        output.set(False)
        assert not output.read()
