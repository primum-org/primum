"""Real GPIO tests: they run only on the Pi (`just test-hw`) with an LED on the test pin.

The pin defaults to GPIO 17 and can be changed with PRIMUM_HW_TEST_PIN.
"""

import os

import pytest

from primum_runtime.hal import OutputSpec

pytestmark = pytest.mark.hw

PIN = int(os.environ.get("PRIMUM_HW_TEST_PIN", "17"))


def test_gpiod_output_starts_off_and_reads_back_what_is_written() -> None:
    from primum_runtime.hal.gpiod_hal import GpiodHal

    with GpiodHal() as hal:
        output = hal.digital_output(OutputSpec(pin=PIN))
        assert not output.read()

        output.set(True)
        assert output.read()

        output.set(False)
        assert not output.read()
