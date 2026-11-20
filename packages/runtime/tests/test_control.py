"""The controller: elements through their drivers, commands, inputs and panic."""

import logging

import pytest

from primum_runtime.board import load_board, load_profile, option_limits
from primum_runtime.control import Controller, InputState, OutputState, State
from primum_runtime.drivers import ElementConfig, load_manifests
from primum_runtime.errors import PrimumError
from primum_runtime.hal import SimulatedHal

BOARD = load_board("rpi4b")
LIMITS = option_limits(load_profile("rpi4b"))
MANIFESTS = load_manifests()

LED = ElementConfig("led", "digital_output", 17, active_low=False)
LAMP = ElementConfig("lamp", "digital_output", 27, active_low=False)
DIMMER = ElementConfig("dimmer", "pwm_output", 18, active_low=False)
BUTTON = ElementConfig("button", "digital_input", 22, active_low=True, options={"pull": "up"})
SPECS = (LED, LAMP)
SWITCH = ("on", "off")  # what a digital output can be asked for
LEVEL = ("on", "off", "set", "fade")  # and a PWM output


@pytest.fixture
def hal() -> SimulatedHal:
    return SimulatedHal(BOARD)


def _controller(hal: SimulatedHal, *elements: ElementConfig) -> Controller:
    return Controller(hal, elements or SPECS, MANIFESTS, LIMITS)


def test_outputs_start_off_in_configuration_order(hal: SimulatedHal) -> None:
    controller = _controller(hal)

    assert controller.state() == State(
        (
            OutputState("led", on=False, level=0, actions=SWITCH),
            OutputState("lamp", on=False, level=0, actions=SWITCH),
        ),
        inputs=(),
        panic=False,
    )


def test_set_output_drives_the_line_and_notifies_the_new_state(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    states: list[State] = []
    controller.subscribe(states.append)

    controller.command("led", "on")

    assert hal.lines[17].active
    assert states == [controller.state()]
    assert states[0].outputs[0] == OutputState("led", on=True, level=100, actions=SWITCH)


def test_unknown_output_raises_output_unknown(hal: SimulatedHal) -> None:
    controller = _controller(hal)

    with pytest.raises(PrimumError) as raised:
        controller.command("fan", "on")

    assert raised.value.code == "output.unknown"
    assert raised.value.params == {"name": "fan"}


def test_panic_turns_every_output_off_and_refuses_commands(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    controller.command("led", "on")

    controller.panic()

    assert not hal.lines[17].active
    assert controller.state().panic
    with pytest.raises(PrimumError) as raised:
        controller.command("led", "on")
    assert raised.value.code == "panic.active"
    assert not hal.lines[17].active


def test_release_panic_accepts_commands_again_with_outputs_still_off(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    controller.panic()

    controller.release_panic()
    state_after_release = controller.state()
    controller.command("led", "on")

    assert not state_after_release.panic
    assert not any(output.on for output in state_after_release.outputs)
    assert hal.lines[17].active


def test_panic_stays_latched_and_notified_when_the_safe_state_fails(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    controller.command("led", "on")
    hal.lines[17].fail_writes(OSError(5, "I/O error"))
    states: list[State] = []
    controller.subscribe(states.append)

    with pytest.raises(PrimumError) as raised:
        controller.panic()

    assert raised.value.code == "hal.safe_state_incomplete"
    assert controller.state().panic
    assert [state.panic for state in states] == [True]


def test_unsubscribed_listener_is_not_called(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    states: list[State] = []
    unsubscribe = controller.subscribe(states.append)

    unsubscribe()
    controller.command("led", "on")

    assert states == []


def test_every_kind_of_element_is_claimed_at_once_through_its_driver(hal: SimulatedHal) -> None:
    controller = _controller(hal, LED, DIMMER, BUTTON)

    assert set(hal.lines) == {17}
    assert set(hal.pwm_lines) == {18}
    assert set(hal.input_lines) == {22}
    assert controller.state() == State(
        (
            OutputState("led", on=False, level=0, actions=SWITCH),
            OutputState("dimmer", on=False, level=0, actions=LEVEL),
        ),
        (InputState("button", active=False),),
        panic=False,
    )


def test_a_command_is_an_action_of_the_driver_with_its_arguments(hal: SimulatedHal) -> None:
    controller = _controller(hal, DIMMER)

    controller.command("dimmer", "set", {"level": 25})

    assert hal.pwm_lines[18].duty == 0.25
    assert controller.state().outputs == (OutputState("dimmer", on=True, level=25, actions=LEVEL),)


def test_an_action_the_output_does_not_have_changes_nothing(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    states: list[State] = []
    controller.subscribe(states.append)

    with pytest.raises(PrimumError) as raised:
        controller.command("led", "set", {"level": 25})

    assert raised.value.code == "element.action_unknown"
    assert raised.value.params == {"element": "led", "action": "set", "available": ("on", "off")}
    assert states == []


def test_an_input_is_not_an_output_to_command(hal: SimulatedHal) -> None:
    controller = _controller(hal, LED, BUTTON)

    with pytest.raises(PrimumError) as raised:
        controller.command("button", "on")

    assert raised.value.code == "output.unknown"


def test_panic_takes_a_pwm_output_to_0_too(hal: SimulatedHal) -> None:
    controller = _controller(hal, LED, DIMMER)
    controller.command("dimmer", "on")

    controller.panic()

    assert hal.pwm_lines[18].duty == 0.0
    assert controller.state().outputs[1] == OutputState("dimmer", on=False, level=0, actions=LEVEL)


def test_reading_the_inputs_takes_their_changes_and_notifies_once(hal: SimulatedHal) -> None:
    controller = _controller(hal, LED, BUTTON)
    states: list[State] = []
    controller.subscribe(states.append)
    hal.simulate_input(22, True)
    hal.simulate_input(22, False)
    hal.simulate_input(22, True)

    controller.read_inputs()

    assert [state.inputs for state in states] == [(InputState("button", active=True),)]


def test_reading_the_inputs_with_nothing_new_notifies_nobody(hal: SimulatedHal) -> None:
    controller = _controller(hal, LED, BUTTON)
    states: list[State] = []
    controller.subscribe(states.append)

    controller.read_inputs()

    assert states == []


def test_an_input_already_active_at_the_start_is_reported_so() -> None:
    hal = SimulatedHal(BOARD)
    # Made by hand to press the button between the claim and the first state.
    controller = _controller(hal, LED, BUTTON)
    hal.simulate_input(22, True)
    controller.read_inputs()

    assert controller.state().inputs == (InputState("button", active=True),)


def test_the_descriptor_to_watch_is_the_hal_s(hal: SimulatedHal) -> None:
    assert _controller(hal, LED, BUTTON).events_fd() == hal.events_fd()


def test_a_wrong_option_fails_before_anything_is_claimed(hal: SimulatedHal) -> None:
    fast = ElementConfig("dimmer", "pwm_output", 18, False, {"frequencyHz": 100_001})

    with pytest.raises(PrimumError) as raised:
        _controller(hal, LED, fast)

    assert raised.value.code == "element.value_out_of_range"
    assert hal.lines == {}


def test_two_elements_of_one_name_are_the_caller_s_mistake(hal: SimulatedHal) -> None:
    with pytest.raises(ValueError, match="same name"):
        _controller(hal, LED, LED)


def test_an_output_that_does_not_follow_is_reported_as_it_reads_and_listeners_are_told(
    hal: SimulatedHal,
) -> None:
    controller = _controller(hal)
    hal.lines[17].stick(False)
    states: list[State] = []
    controller.subscribe(states.append)

    with pytest.raises(PrimumError) as raised:
        controller.command("led", "on")

    assert raised.value.code == "element.level_not_reached"
    assert controller.state().outputs[0] == OutputState("led", on=False, level=0, actions=SWITCH)
    assert states == [controller.state()]


def test_a_pwm_output_that_does_not_follow_reports_the_level_it_reads(hal: SimulatedHal) -> None:
    controller = _controller(hal, DIMMER)
    hal.pwm_lines[18].stick(0.2)

    with pytest.raises(PrimumError):
        controller.command("dimmer", "set", {"level": 80})

    assert controller.state().outputs == (OutputState("dimmer", on=True, level=20, actions=LEVEL),)


def test_the_next_command_that_is_followed_says_what_it_did(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    hal.lines[17].stick(False)
    with pytest.raises(PrimumError):
        controller.command("led", "on")
    hal.lines[17].stick(None)

    controller.command("led", "on")

    assert controller.state().outputs[0] == OutputState("led", on=True, level=100, actions=SWITCH)


def test_panic_after_an_output_did_not_follow_reports_its_safe_state(hal: SimulatedHal) -> None:
    controller = _controller(hal, DIMMER)
    hal.pwm_lines[18].stick(0.2)
    with pytest.raises(PrimumError):
        controller.command("dimmer", "set", {"level": 80})
    hal.pwm_lines[18].stick(None)

    controller.panic()

    assert controller.state().outputs == (OutputState("dimmer", on=False, level=0, actions=LEVEL),)


def test_a_reading_from_before_panic_does_not_outlive_it(hal: SimulatedHal) -> None:
    """Off is asked and the line stays on; it recovers, and panic turns it off. Panic writes
    the same level the failed command did, and the state must still say what the line reads."""
    controller = _controller(hal)
    controller.command("led", "on")
    hal.lines[17].stick(True)
    with pytest.raises(PrimumError):
        controller.command("led", "off")
    assert controller.state().outputs[0].on
    hal.lines[17].stick(None)

    controller.panic()
    after_panic = controller.state()
    controller.release_panic()

    assert not after_panic.outputs[0].on
    assert not controller.state().outputs[0].on


def test_an_output_that_recovers_on_its_own_is_reported_as_it_now_reads(hal: SimulatedHal) -> None:
    """On is asked and the line stays off, written on. When it follows at last, it is on."""
    controller = _controller(hal)
    hal.lines[17].stick(False)
    with pytest.raises(PrimumError):
        controller.command("led", "on")
    assert not controller.state().outputs[0].on

    hal.lines[17].stick(None)

    assert controller.state().outputs[0] == OutputState("led", on=True, level=100, actions=SWITCH)


def test_the_state_can_still_be_told_after_the_hal_is_closed(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    hal.lines[17].stick(False)
    with pytest.raises(PrimumError):
        controller.command("led", "on")
    hal.lines[17].stick(None)

    hal.close()

    assert controller.state().outputs[0] == OutputState("led", on=False, level=0, actions=SWITCH)


def _unsure_led_whose_reads_fail(hal: SimulatedHal) -> Controller:
    """The LED did not follow a command, and then its line cannot even be read."""
    controller = _controller(hal)
    hal.lines[17].stick(False)
    with pytest.raises(PrimumError):
        controller.command("led", "on")
    hal.lines[17].fail_reads(OSError(5, "I/O error"))
    return controller


def test_a_level_that_cannot_be_read_does_not_break_the_state(
    hal: SimulatedHal, caplog: pytest.LogCaptureFixture
) -> None:
    controller = _unsure_led_whose_reads_fail(hal)

    state = controller.state()

    assert state.outputs[0] == OutputState(
        "led", on=True, level=100, actions=SWITCH
    )  # what was written
    assert "led" in caplog.text
    assert "I/O error" in caplog.text


def test_a_level_that_cannot_be_read_does_not_hide_a_failed_safe_state(hal: SimulatedHal) -> None:
    controller = _unsure_led_whose_reads_fail(hal)
    states: list[State] = []
    controller.subscribe(states.append)

    with pytest.raises(PrimumError) as raised:
        controller.panic()

    assert raised.value.code == "hal.safe_state_incomplete"
    assert [state.panic for state in states] == [True]


def test_on_and_level_come_from_one_reading(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    hal.lines[17].stick(False)
    with pytest.raises(PrimumError):
        controller.command("led", "on")
    readings = iter([True, False])
    hal.lines[17].read = lambda: next(readings)  # type: ignore[method-assign]  # a line that flickers

    assert controller.state().outputs[0] == OutputState("led", on=True, level=100, actions=SWITCH)


# --- test mode: commands that expire on their own (decision 0006) ---------------------------


class Clock:
    """A monotonic clock a test moves by hand."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _timed(hal: SimulatedHal, *elements: ElementConfig) -> tuple[Controller, Clock]:
    clock = Clock()
    return Controller(hal, elements or SPECS, MANIFESTS, LIMITS, clock=clock), clock


def test_a_test_turns_the_output_on_and_says_how_long_is_left(hal: SimulatedHal) -> None:
    controller, clock = _timed(hal)

    controller.command("led", "on", duration_ms=10_000)
    clock.now += 4

    assert hal.lines[17].active
    assert controller.state().outputs[0].remaining_ms == 6_000
    assert controller.next_expiry_s() == 6.0


def test_a_test_that_has_run_out_sends_the_output_to_rest_and_tells_the_listeners(
    hal: SimulatedHal,
) -> None:
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=10_000)
    states: list[State] = []
    controller.subscribe(states.append)

    clock.now += 10
    controller.expire()

    assert not hal.lines[17].active
    assert states == [controller.state()]
    assert states[0].outputs[0] == OutputState("led", on=False, level=0, actions=SWITCH)
    assert controller.next_expiry_s() is None


def test_expiring_before_time_changes_nothing_and_tells_nobody(hal: SimulatedHal) -> None:
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=10_000)
    states: list[State] = []
    controller.subscribe(states.append)

    clock.now += 9.9
    controller.expire()

    assert hal.lines[17].active
    assert states == []


def test_a_test_of_a_level_rests_at_0(hal: SimulatedHal) -> None:
    controller, clock = _timed(hal, DIMMER)
    controller.command("dimmer", "set", {"level": 40}, duration_ms=5_000)

    clock.now += 5
    controller.expire()

    assert hal.pwm_lines[18].duty == 0.0


def test_each_output_expires_at_its_own_time(hal: SimulatedHal) -> None:
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=2_000)
    controller.command("lamp", "on", duration_ms=5_000)

    clock.now += 3
    controller.expire()

    assert [line.active for line in (hal.lines[17], hal.lines[27])] == [False, True]
    assert controller.next_expiry_s() == 2.0


def test_a_command_without_a_duration_ends_the_test_and_stays(hal: SimulatedHal) -> None:
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=2_000)

    controller.command("led", "on")
    clock.now += 60
    controller.expire()

    assert hal.lines[17].active
    assert controller.state().outputs[0].remaining_ms is None


def test_a_new_test_starts_its_time_again(hal: SimulatedHal) -> None:
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=2_000)
    clock.now += 1.5

    controller.command("led", "on", duration_ms=2_000)

    assert controller.state().outputs[0].remaining_ms == 2_000


@pytest.mark.parametrize("duration_ms", [0, 999, 300_001, -5])
def test_a_test_lasts_from_a_second_to_five_minutes(hal: SimulatedHal, duration_ms: int) -> None:
    controller, _ = _timed(hal)

    with pytest.raises(PrimumError) as raised:
        controller.command("led", "on", duration_ms=duration_ms)

    assert raised.value.code == "test.duration_out_of_range"
    assert raised.value.params == {
        "duration_ms": duration_ms,
        "min_ms": 1_000,
        "max_ms": 300_000,
    }
    assert not hal.lines[17].active


@pytest.mark.parametrize("duration_ms", [1_000, 300_000])
def test_both_ends_of_what_a_test_may_last_are_taken(hal: SimulatedHal, duration_ms: int) -> None:
    controller, _ = _timed(hal)

    controller.command("led", "on", duration_ms=duration_ms)

    assert controller.state().outputs[0].remaining_ms == duration_ms


def test_panic_ends_every_test_and_releasing_it_brings_nothing_back(hal: SimulatedHal) -> None:
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=10_000)

    controller.panic()
    controller.release_panic()
    clock.now += 60
    controller.expire()

    assert not hal.lines[17].active
    assert controller.state().outputs[0].remaining_ms is None
    assert controller.next_expiry_s() is None


def test_a_command_that_fails_starts_no_test(hal: SimulatedHal) -> None:
    controller, _ = _timed(hal)

    with pytest.raises(PrimumError):
        controller.command("led", "set", {"level": 5}, duration_ms=10_000)

    assert controller.next_expiry_s() is None


def test_a_test_the_output_did_not_follow_still_expires(hal: SimulatedHal) -> None:
    """The output was written, whatever it reads back: it must be sent to rest all the same."""
    controller, clock = _timed(hal)
    hal.lines[17].stick(False)
    with pytest.raises(PrimumError):
        controller.command("led", "on", duration_ms=2_000)
    hal.lines[17].stick(None)
    assert hal.lines[17].active

    clock.now += 2
    controller.expire()

    assert not hal.lines[17].active


def test_an_output_that_cannot_be_sent_to_rest_does_not_stop_the_others(
    hal: SimulatedHal, caplog: pytest.LogCaptureFixture
) -> None:
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=2_000)
    controller.command("lamp", "on", duration_ms=2_000)
    hal.lines[17].stick(True)

    clock.now += 2
    controller.expire()

    assert not hal.lines[27].active
    assert "the test of led expired and it could not be sent to rest" in caplog.text


def test_whatever_the_hardware_raises_does_not_stop_the_others_either(
    hal: SimulatedHal,
) -> None:
    """The real HAL lets an ``OSError`` of a line through as it is: if it escaped ``expire``,
    the timer would never be armed again and the lamp would stay on for good."""
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=2_000)
    controller.command("lamp", "on", duration_ms=2_000)
    hal.lines[17].fail_writes(OSError(5, "I/O error"))

    clock.now += 2
    controller.expire()

    assert not hal.lines[27].active
    assert controller.state().outputs[1].remaining_ms is None


def test_an_output_that_could_not_rest_says_so_and_is_tried_again(hal: SimulatedHal) -> None:
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=2_000)
    hal.lines[17].fail_writes(OSError(5, "I/O error"))
    states: list[State] = []
    controller.subscribe(states.append)

    clock.now += 2
    controller.expire()

    led = controller.state().outputs[0]
    assert (led.on, led.remaining_ms, led.rest_failed) == (True, None, True)
    assert [state.outputs[0].rest_failed for state in states] == [True]
    assert controller.next_expiry_s() == 5.0  # when it is tried again

    hal.lines[17].fail_writes(None)
    clock.now += 5
    controller.expire()

    led = controller.state().outputs[0]
    assert (led.on, led.rest_failed) == (False, False)
    assert controller.next_expiry_s() is None


def test_it_goes_on_trying_while_the_output_cannot_rest(hal: SimulatedHal) -> None:
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=2_000)
    hal.lines[17].fail_writes(OSError(5, "I/O error"))

    for wait in (2, 5, 5, 5):
        clock.now += wait
        controller.expire()

    assert controller.state().outputs[0].rest_failed
    assert controller.next_expiry_s() == 5.0


def test_a_command_or_panic_ends_the_trying(hal: SimulatedHal) -> None:
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=2_000)
    hal.lines[17].fail_writes(OSError(5, "I/O error"))
    clock.now += 2
    controller.expire()
    hal.lines[17].fail_writes(None)

    controller.command("led", "on")

    assert not controller.state().outputs[0].rest_failed
    assert controller.next_expiry_s() is None


def test_a_test_whose_read_back_fails_still_expires(hal: SimulatedHal) -> None:
    """The output was written and then could not be read: whatever that raises, it is on
    and it is a test, so it must still be sent to rest."""
    controller, clock = _timed(hal)
    hal.lines[17].fail_reads(OSError(5, "I/O error"))
    states: list[State] = []
    controller.subscribe(states.append)

    with pytest.raises(OSError, match="I/O error"):
        controller.command("led", "on", duration_ms=2_000)

    assert hal.lines[17].active
    assert controller.next_expiry_s() == 2.0
    assert len(states) == 1  # the output changed: listeners are told

    hal.lines[17].fail_reads(None)
    clock.now += 2
    controller.expire()

    assert not hal.lines[17].active


def test_a_command_that_fails_after_writing_does_not_end_a_test_under_way(
    hal: SimulatedHal,
) -> None:
    """Without a duration it would have ended the test; failed, it leaves the output in a
    state nobody knows, and the test's deadline is what still sends it to rest."""
    controller, _ = _timed(hal)
    controller.command("led", "on", duration_ms=2_000)
    hal.lines[17].fail_reads(OSError(5, "I/O error"))

    with pytest.raises(OSError, match="I/O error"):
        controller.command("led", "on")

    assert controller.next_expiry_s() == 2.0


def test_a_command_refused_before_writing_leaves_a_test_under_way_as_it_was(
    hal: SimulatedHal,
) -> None:
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=2_000)
    clock.now += 0.5

    with pytest.raises(PrimumError):
        controller.command("led", "blink", duration_ms=60_000)

    assert controller.next_expiry_s() == 1.5
    assert hal.lines[17].history == (True,)


def test_panic_ends_the_trying_too(hal: SimulatedHal) -> None:
    """After panic nothing is tried again, so nothing may go on saying that it is."""
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=2_000)
    hal.lines[17].fail_reads(OSError(5, "I/O error"))  # written off, never confirmed
    clock.now += 2
    controller.expire()
    assert controller.state().outputs[0].rest_failed
    hal.lines[17].fail_reads(None)

    controller.panic()

    assert not controller.state().outputs[0].rest_failed
    assert controller.next_expiry_s() is None


def test_an_output_that_goes_on_failing_is_logged_once_and_again_when_it_rests(
    hal: SimulatedHal, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    controller, clock = _timed(hal)
    controller.command("led", "on", duration_ms=2_000)
    hal.lines[17].fail_writes(OSError(5, "I/O error"))
    for wait in (2, 5, 5, 5):
        clock.now += wait
        controller.expire()
    failures = [
        record for record in caplog.records if "could not be sent to rest" in record.message
    ]

    hal.lines[17].fail_writes(None)
    clock.now += 5
    controller.expire()

    assert len(failures) == 1
    assert "led is at rest after all" in caplog.text
