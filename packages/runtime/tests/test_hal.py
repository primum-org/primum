"""The HAL through its simulated implementation: claiming, the safe state, closing, faults."""

import subprocess
import sys
import types

import pytest

from primum_runtime.board import load_board
from primum_runtime.errors import PrimumError
from primum_runtime.hal import (
    Claim,
    InputEvent,
    InputSpec,
    OutputSpec,
    Pull,
    PwmSpec,
    SimulatedHal,
    create_hal,
)

BOARD = load_board("rpi4b")

LED = OutputSpec(pin=17)
RELAY = OutputSpec(pin=27, active_low=True)
BUTTON = InputSpec(pin=22, pull=Pull.UP, active_low=True, debounce_ms=20)
FAN = PwmSpec(pin=18, frequency_hz=25_000)
EVERYTHING = Claim(outputs=(LED, RELAY), inputs=(BUTTON,), pwms=(FAN,))


def _claimed(claim: Claim = EVERYTHING) -> SimulatedHal:
    hal = SimulatedHal(BOARD)
    hal.claim(claim)
    return hal


def test_outputs_start_in_safe_state() -> None:
    with _claimed() as hal:
        assert not hal.outputs[17].is_on
        assert not hal.lines[17].active
        assert hal.lines[17].history == ()
        assert hal.pwms[18].duty == 0.0


def test_set_turns_the_line_on_and_off() -> None:
    with _claimed() as hal:
        output = hal.outputs[17]

        output.set(True)
        assert output.is_on
        output.set(False)

        assert hal.lines[17].history == (True, False)


def test_active_low_output_drives_the_pin_low_when_on() -> None:
    with _claimed() as hal:
        assert hal.lines[27].level_high
        hal.outputs[27].set(True)
        assert not hal.lines[27].level_high


def test_a_pwm_output_takes_a_level_from_0_to_1() -> None:
    with _claimed() as hal:
        fan = hal.pwms[18]

        fan.set(0.5)

        assert fan.duty == fan.read() == 0.5
        assert hal.pwm_lines[18].history == (0.5,)


@pytest.mark.parametrize("duty", [-0.1, 1.5])
def test_a_level_outside_0_to_1_is_refused(duty: float) -> None:
    with _claimed() as hal, pytest.raises(PrimumError) as raised:
        hal.pwms[18].set(duty)

    assert raised.value.code == "hal.duty_out_of_range"
    assert raised.value.params == {"duty": duty}


def test_an_input_is_read_and_reports_each_change_as_an_event() -> None:
    with _claimed() as hal:
        button = hal.inputs[22]
        assert not button.read()
        assert not hal.wait_events(1.0)

        hal.simulate_input(22, True, timestamp_ns=1_000)
        hal.simulate_input(22, True, timestamp_ns=2_000)  # no change: no event
        hal.simulate_input(22, False, timestamp_ns=3_000)

        assert hal.wait_events(0)
        assert hal.read_events() == [InputEvent(22, True, 1_000), InputEvent(22, False, 3_000)]
        assert hal.read_events() == []
        assert not button.read()


def test_the_claim_is_made_once() -> None:
    with _claimed() as hal, pytest.raises(PrimumError) as raised:
        hal.claim(Claim(outputs=(OutputSpec(pin=5),)))

    assert raised.value.code == "hal.already_claimed"


def test_a_pin_asked_for_twice_fails_with_pin_in_use_before_anything_is_claimed() -> None:
    hal = SimulatedHal(BOARD)

    with pytest.raises(PrimumError) as raised:
        hal.claim(Claim(outputs=(LED,), inputs=(InputSpec(pin=17),)))

    assert raised.value.code == "hal.pin_in_use"
    assert raised.value.params == {"pin": 17}
    assert hal.lines == {}


@pytest.mark.parametrize("pin", [-1, 28])
def test_a_pin_the_board_does_not_have_raises_pin_invalid(pin: int) -> None:
    with SimulatedHal(BOARD) as hal, pytest.raises(PrimumError) as raised:
        hal.claim(Claim(outputs=(OutputSpec(pin=pin),)))

    assert raised.value.code == "hal.pin_invalid"
    assert raised.value.params == {"pin": pin, "board": "rpi4b"}
    assert hal.lines == {}


def test_a_pwm_output_needs_a_pin_with_hardware_pwm() -> None:
    with SimulatedHal(BOARD) as hal, pytest.raises(PrimumError) as raised:
        hal.claim(Claim(pwms=(PwmSpec(pin=17),)))

    assert raised.value.code == "hal.pwm_unsupported_pin"
    assert raised.value.params == {"pin": 17, "board": "rpi4b"}


def test_apply_safe_state_turns_every_output_off_and_every_pwm_to_zero() -> None:
    with _claimed() as hal:
        hal.outputs[17].set(True)
        hal.outputs[27].set(True)
        hal.pwms[18].set(0.8)

        hal.apply_safe_state()

        assert not hal.outputs[17].is_on
        assert not hal.outputs[27].is_on
        assert hal.pwms[18].duty == 0.0


def test_apply_safe_state_reads_every_output_back() -> None:
    hal = _claimed()
    hal.outputs[17].set(True)
    hal.lines[17].stick(True)  # whatever is written, the line reads back on

    with pytest.raises(PrimumError) as raised:
        hal.apply_safe_state()

    assert raised.value.code == "hal.safe_state_unverified"
    assert raised.value.params == {"pins": (17,)}


def test_close_applies_safe_state_and_releases_lines() -> None:
    hal = _claimed()
    hal.outputs[17].set(True)
    hal.pwms[18].set(0.5)

    hal.close()

    assert not hal.lines[17].active
    assert hal.lines[17].released
    assert hal.pwm_lines[18].duty == 0.0
    assert hal.pwm_lines[18].released


def test_leaving_the_with_block_on_an_exception_applies_safe_state() -> None:
    hal = _claimed()

    with pytest.raises(KeyboardInterrupt), hal:
        hal.outputs[17].set(True)
        raise KeyboardInterrupt

    assert not hal.lines[17].active
    assert hal.lines[17].released


def test_closed_hal_rejects_claims_writes_and_reads() -> None:
    hal = _claimed()
    output = hal.outputs[17]
    hal.close()

    with pytest.raises(PrimumError) as on_write:
        output.set(True)
    with pytest.raises(PrimumError) as on_claim:
        hal.claim(Claim())
    with pytest.raises(PrimumError) as on_events:
        hal.read_events()

    assert on_write.value.code == on_claim.value.code == on_events.value.code == "hal.closed"


def test_closing_twice_does_nothing() -> None:
    hal = SimulatedHal(BOARD)
    hal.close()
    hal.close()


def test_create_hal_returns_the_simulated_hal_when_simulating() -> None:
    assert isinstance(create_hal(simulate=True, board=BOARD), SimulatedHal)


def test_create_hal_without_gpiod_raises_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "gpiod", None)  # what `import gpiod` finds on macOS
    monkeypatch.delitem(sys.modules, "primum_runtime.hal.gpiod_hal", raising=False)

    with pytest.raises(PrimumError) as raised:
        create_hal(simulate=False, board=BOARD)

    assert raised.value.code == "hal.unsupported_platform"
    assert raised.value.params == {"platform": sys.platform}


def test_create_hal_with_a_broken_gpiod_raises_gpio_library_broken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # gpiod is there but a part of it is not: what a wheel built for another CPU looks like.
    monkeypatch.setitem(sys.modules, "gpiod", types.ModuleType("gpiod"))
    monkeypatch.setitem(sys.modules, "gpiod.line", None)
    monkeypatch.delitem(sys.modules, "primum_runtime.hal.gpiod_hal", raising=False)

    with pytest.raises(PrimumError) as raised:
        create_hal(simulate=False, board=BOARD)

    assert raised.value.code == "hal.gpio_library_broken"
    assert "gpiod.line" in str(raised.value.params["detail"])


def test_simulated_hal_does_not_import_gpiod() -> None:
    # A fresh interpreter: other tests may have imported gpiod in this one.
    code = (
        "import sys\n"
        "from primum_runtime.board import load_board\n"
        "from primum_runtime.hal import create_hal\n"
        "create_hal(simulate=True, board=load_board('rpi4b'))\n"
        "sys.exit('gpiod' in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", code], check=False)  # noqa: S603 (fixed code)

    assert result.returncode == 0


def test_read_reports_the_state_of_the_line() -> None:
    with _claimed() as hal:
        hal.outputs[17].set(True)

        assert hal.outputs[17].read()


def test_failed_write_keeps_the_last_commanded_state() -> None:
    # No `with` block: closing a HAL with a faulty line raises, and would hide a failed assert.
    hal = _claimed()
    output = hal.outputs[17]
    hal.lines[17].fail_writes(OSError(5, "I/O error"))

    with pytest.raises(OSError):
        output.set(True)

    assert not output.is_on


def test_apply_safe_state_turns_off_the_other_outputs_when_one_fails() -> None:
    hal = _claimed()
    hal.outputs[17].set(True)
    hal.outputs[27].set(True)
    hal.lines[17].fail_writes(OSError(5, "I/O error"))

    with pytest.raises(PrimumError) as raised:
        hal.apply_safe_state()

    assert raised.value.code == "hal.safe_state_incomplete"
    assert raised.value.params == {"pins": (17,)}
    assert isinstance(raised.value.__cause__, ExceptionGroup)
    assert not hal.lines[27].active


def test_close_releases_every_line_even_if_the_safe_state_fails() -> None:
    hal = _claimed()
    hal.outputs[17].set(True)
    hal.outputs[27].set(True)
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
    hal = _claimed()
    hal.lines[17].fail_release(OSError(5, "I/O error"))

    with pytest.raises(PrimumError) as raised:
        hal.close()

    assert raised.value.code == "hal.release_incomplete"
    assert raised.value.params == {"pins": (17,)}
    assert hal.lines[27].released
    assert hal.pwm_lines[18].released
    with pytest.raises(PrimumError):
        hal.ensure_open()


def test_failed_safe_state_on_leaving_with_replaces_the_original_exception() -> None:
    hal = _claimed()
    original = KeyboardInterrupt()

    with pytest.raises(PrimumError) as raised, hal:
        hal.outputs[17].set(True)
        hal.lines[17].fail_writes(OSError(5, "I/O error"))
        raise original

    assert raised.value.code == "hal.safe_state_incomplete"
    assert raised.value.__context__ is original


def test_close_reports_safe_state_and_release_failures_together() -> None:
    hal = _claimed()
    hal.outputs[17].set(True)
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


def test_close_reports_an_unverified_safe_state_with_the_release_failures() -> None:
    hal = _claimed()
    hal.lines[17].stick(True)
    hal.lines[27].fail_release(OSError(16, "Device or resource busy"))

    with pytest.raises(PrimumError) as raised:
        hal.close()

    assert raised.value.code == "hal.safe_state_unverified"
    assert raised.value.params == {"pins": (17,), "release_pins": (27,)}
