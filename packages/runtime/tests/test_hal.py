import subprocess
import sys

import pytest

from primum_runtime.errors import PrimumError
from primum_runtime.hal import OutputSpec, SimulatedHal, create_hal

LED = OutputSpec(pin=17)
RELAY = OutputSpec(pin=27, active_low=True)


def test_digital_output_starts_in_safe_state() -> None:
    with SimulatedHal() as hal:
        output = hal.digital_output(LED)

        assert not output.is_on
        assert not hal.lines[17].active
        assert hal.lines[17].history == ()


def test_set_turns_the_line_on_and_off() -> None:
    with SimulatedHal() as hal:
        output = hal.digital_output(LED)

        output.set(True)
        output.set(False)

        assert hal.lines[17].history == (True, False)
        assert not output.is_on


def test_active_low_output_drives_the_pin_low_when_on() -> None:
    with SimulatedHal() as hal:
        relay = hal.digital_output(RELAY)

        assert hal.lines[27].level_high
        relay.set(True)
        assert not hal.lines[27].level_high


def test_claiming_a_pin_twice_fails_with_pin_in_use() -> None:
    with SimulatedHal() as hal:
        hal.digital_output(LED)

        with pytest.raises(PrimumError) as raised:
            hal.digital_output(OutputSpec(pin=17))

        assert raised.value.code == "hal.pin_in_use"
        assert raised.value.params == {"pin": 17}


def test_apply_safe_state_turns_every_output_off() -> None:
    with SimulatedHal() as hal:
        led = hal.digital_output(LED)
        relay = hal.digital_output(RELAY)
        led.set(True)
        relay.set(True)

        hal.apply_safe_state()

        assert not led.is_on
        assert not relay.is_on


def test_close_applies_safe_state_and_releases_lines() -> None:
    hal = SimulatedHal()
    hal.digital_output(LED).set(True)
    line = hal.lines[17]

    hal.close()

    assert not line.active
    assert line.released


def test_leaving_the_with_block_on_an_exception_applies_safe_state() -> None:
    hal = SimulatedHal()

    with pytest.raises(KeyboardInterrupt), hal:
        hal.digital_output(LED).set(True)
        raise KeyboardInterrupt

    assert not hal.lines[17].active
    assert hal.lines[17].released


def test_closed_hal_rejects_new_outputs_and_writes() -> None:
    hal = SimulatedHal()
    output = hal.digital_output(LED)
    hal.close()

    with pytest.raises(PrimumError) as on_write:
        output.set(True)
    with pytest.raises(PrimumError) as on_claim:
        hal.digital_output(RELAY)

    assert on_write.value.code == on_claim.value.code == "hal.closed"


def test_closing_twice_does_nothing() -> None:
    hal = SimulatedHal()
    hal.close()
    hal.close()


def test_create_hal_returns_the_simulated_hal_when_simulating() -> None:
    assert isinstance(create_hal(simulate=True), SimulatedHal)


def test_simulated_hal_does_not_import_gpiod() -> None:
    # A fresh interpreter: other tests may have imported gpiod in this one.
    code = "import sys; from primum_runtime.hal import create_hal; create_hal(simulate=True); "
    code += "sys.exit('gpiod' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], check=False)  # noqa: S603 (fixed code)

    assert result.returncode == 0
