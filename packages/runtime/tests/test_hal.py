import subprocess
import sys
import types

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


def test_negative_pin_raises_pin_invalid_before_reaching_a_hal() -> None:
    with pytest.raises(PrimumError) as raised:
        OutputSpec(pin=-1)

    assert raised.value.code == "hal.pin_invalid"
    assert raised.value.params == {"pin": -1}


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


def test_create_hal_without_gpiod_raises_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # As on macOS or Windows, where gpiod is not installed.
    monkeypatch.setitem(sys.modules, "gpiod", None)
    monkeypatch.delitem(sys.modules, "primum_runtime.hal.gpiod_hal", raising=False)

    with pytest.raises(PrimumError) as raised:
        create_hal(simulate=False)

    assert raised.value.code == "hal.unsupported_platform"
    assert raised.value.params == {"platform": sys.platform}


def test_create_hal_with_a_broken_gpiod_raises_gpio_library_broken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # gpiod is there but part of it is missing, as when its C extension did not build.
    monkeypatch.setitem(sys.modules, "gpiod", types.ModuleType("gpiod"))
    monkeypatch.setitem(sys.modules, "gpiod.line", None)
    monkeypatch.delitem(sys.modules, "primum_runtime.hal.gpiod_hal", raising=False)

    with pytest.raises(PrimumError) as raised:
        create_hal(simulate=False)

    assert raised.value.code == "hal.gpio_library_broken"
    assert "gpiod.line" in str(raised.value.params["detail"])


def test_simulated_hal_does_not_import_gpiod() -> None:
    # A fresh interpreter: other tests may have imported gpiod in this one.
    code = "import sys; from primum_runtime.hal import create_hal; create_hal(simulate=True); "
    code += "sys.exit('gpiod' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], check=False)  # noqa: S603 (fixed code)

    assert result.returncode == 0


def test_read_reports_the_state_of_the_line() -> None:
    with SimulatedHal() as hal:
        output = hal.digital_output(LED)

        output.set(True)

        assert output.read()


def test_failed_write_keeps_the_last_commanded_state() -> None:
    # No `with` block: closing a HAL with a faulty line raises, and would hide a failed assert.
    hal = SimulatedHal()
    output = hal.digital_output(LED)
    hal.lines[17].fail_writes(OSError(5, "I/O error"))

    with pytest.raises(OSError):
        output.set(True)

    assert not output.is_on


def test_apply_safe_state_turns_off_the_other_outputs_when_one_fails() -> None:
    hal = SimulatedHal()
    led = hal.digital_output(LED)
    relay = hal.digital_output(RELAY)
    led.set(True)
    relay.set(True)
    hal.lines[17].fail_writes(OSError(5, "I/O error"))

    with pytest.raises(PrimumError) as raised:
        hal.apply_safe_state()

    assert raised.value.code == "hal.safe_state_incomplete"
    assert raised.value.params == {"pins": (17,)}
    assert isinstance(raised.value.__cause__, ExceptionGroup)
    assert not hal.lines[27].active


def test_close_releases_every_line_even_if_the_safe_state_fails() -> None:
    hal = SimulatedHal()
    hal.digital_output(LED).set(True)
    hal.digital_output(RELAY).set(True)
    hal.lines[17].fail_writes(OSError(5, "I/O error"))

    with pytest.raises(PrimumError) as raised:
        hal.close()

    assert raised.value.code == "hal.safe_state_incomplete"
    assert not hal.lines[27].active
    assert hal.lines[17].released
    assert hal.lines[27].released
    with pytest.raises(PrimumError):
        hal.ensure_open()


def test_close_releases_the_other_lines_when_one_release_fails() -> None:
    hal = SimulatedHal()
    hal.digital_output(LED)
    hal.digital_output(RELAY)
    hal.lines[17].fail_release(OSError(5, "I/O error"))

    with pytest.raises(PrimumError) as raised:
        hal.close()

    assert raised.value.code == "hal.release_incomplete"
    assert raised.value.params == {"pins": (17,)}
    assert hal.lines[27].released
    with pytest.raises(PrimumError):
        hal.ensure_open()


def test_failed_safe_state_on_leaving_with_replaces_the_original_exception() -> None:
    hal = SimulatedHal()
    original = KeyboardInterrupt()

    with pytest.raises(PrimumError) as raised, hal:
        hal.digital_output(LED).set(True)
        hal.lines[17].fail_writes(OSError(5, "I/O error"))
        raise original

    assert raised.value.code == "hal.safe_state_incomplete"
    assert raised.value.__context__ is original


def test_close_reports_safe_state_and_release_failures_together() -> None:
    hal = SimulatedHal()
    hal.digital_output(LED).set(True)
    hal.digital_output(RELAY)
    write_error = OSError(5, "I/O error")
    release_error = OSError(16, "Device or resource busy")
    hal.lines[17].fail_writes(write_error)
    hal.lines[27].fail_release(release_error)

    with pytest.raises(PrimumError) as raised:
        hal.close()

    assert raised.value.code == "hal.safe_state_incomplete"
    assert raised.value.params == {"pins": (17,), "release_pins": (27,)}
    cause = raised.value.__cause__
    assert isinstance(cause, ExceptionGroup)
    # isinstance cannot narrow the group's type parameter, so pyright sees it as unknown.
    assert cause.exceptions == (write_error, release_error)  # pyright: ignore[reportUnknownMemberType]
