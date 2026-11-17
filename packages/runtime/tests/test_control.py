"""The controller: elements through their drivers, commands, inputs and panic."""

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


@pytest.fixture
def hal() -> SimulatedHal:
    return SimulatedHal(BOARD)


def _controller(hal: SimulatedHal, *elements: ElementConfig) -> Controller:
    return Controller(hal, elements or SPECS, MANIFESTS, LIMITS)


def test_outputs_start_off_in_configuration_order(hal: SimulatedHal) -> None:
    controller = _controller(hal)

    assert controller.state() == State(
        (OutputState("led", on=False, level=0), OutputState("lamp", on=False, level=0)),
        inputs=(),
        panic=False,
    )


def test_set_output_drives_the_line_and_notifies_the_new_state(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    states: list[State] = []
    controller.subscribe(states.append)

    controller.set_output("led", True)

    assert hal.lines[17].active
    assert states == [controller.state()]
    assert states[0].outputs[0] == OutputState("led", on=True, level=100)


def test_unknown_output_raises_output_unknown(hal: SimulatedHal) -> None:
    controller = _controller(hal)

    with pytest.raises(PrimumError) as raised:
        controller.set_output("fan", True)

    assert raised.value.code == "output.unknown"
    assert raised.value.params == {"name": "fan"}


def test_panic_turns_every_output_off_and_refuses_commands(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    controller.set_output("led", True)

    controller.panic()

    assert not hal.lines[17].active
    assert controller.state().panic
    with pytest.raises(PrimumError) as raised:
        controller.set_output("led", True)
    assert raised.value.code == "panic.active"
    assert not hal.lines[17].active


def test_release_panic_accepts_commands_again_with_outputs_still_off(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    controller.panic()

    controller.release_panic()
    state_after_release = controller.state()
    controller.set_output("led", True)

    assert not state_after_release.panic
    assert not any(output.on for output in state_after_release.outputs)
    assert hal.lines[17].active


def test_panic_stays_latched_and_notified_when_the_safe_state_fails(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    controller.set_output("led", True)
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
    controller.set_output("led", True)

    assert states == []


def test_every_kind_of_element_is_claimed_at_once_through_its_driver(hal: SimulatedHal) -> None:
    controller = _controller(hal, LED, DIMMER, BUTTON)

    assert set(hal.lines) == {17}
    assert set(hal.pwm_lines) == {18}
    assert set(hal.input_lines) == {22}
    assert controller.state() == State(
        (OutputState("led", on=False, level=0), OutputState("dimmer", on=False, level=0)),
        (InputState("button", active=False),),
        panic=False,
    )


def test_a_command_is_an_action_of_the_driver_with_its_arguments(hal: SimulatedHal) -> None:
    controller = _controller(hal, DIMMER)

    controller.command("dimmer", "set", {"level": 25})

    assert hal.pwm_lines[18].duty == 0.25
    assert controller.state().outputs == (OutputState("dimmer", on=True, level=25),)


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
    assert controller.state().outputs[1] == OutputState("dimmer", on=False, level=0)


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
        controller.set_output("led", True)

    assert raised.value.code == "element.level_not_reached"
    assert controller.state().outputs[0] == OutputState("led", on=False, level=0)
    assert states == [controller.state()]


def test_a_pwm_output_that_does_not_follow_reports_the_level_it_reads(hal: SimulatedHal) -> None:
    controller = _controller(hal, DIMMER)
    hal.pwm_lines[18].stick(0.2)

    with pytest.raises(PrimumError):
        controller.command("dimmer", "set", {"level": 80})

    assert controller.state().outputs == (OutputState("dimmer", on=True, level=20),)


def test_the_next_command_that_is_followed_says_what_it_did(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    hal.lines[17].stick(False)
    with pytest.raises(PrimumError):
        controller.set_output("led", True)
    hal.lines[17].stick(None)

    controller.set_output("led", True)

    assert controller.state().outputs[0] == OutputState("led", on=True, level=100)


def test_panic_after_an_output_did_not_follow_reports_its_safe_state(hal: SimulatedHal) -> None:
    controller = _controller(hal, DIMMER)
    hal.pwm_lines[18].stick(0.2)
    with pytest.raises(PrimumError):
        controller.command("dimmer", "set", {"level": 80})
    hal.pwm_lines[18].stick(None)

    controller.panic()

    assert controller.state().outputs == (OutputState("dimmer", on=False, level=0),)


def test_a_reading_from_before_panic_does_not_outlive_it(hal: SimulatedHal) -> None:
    """Off is asked and the line stays on; it recovers, and panic turns it off. Panic writes
    the same level the failed command did, and the state must still say what the line reads."""
    controller = _controller(hal)
    controller.set_output("led", True)
    hal.lines[17].stick(True)
    with pytest.raises(PrimumError):
        controller.set_output("led", False)
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
        controller.set_output("led", True)
    assert not controller.state().outputs[0].on

    hal.lines[17].stick(None)

    assert controller.state().outputs[0] == OutputState("led", on=True, level=100)


def test_the_state_can_still_be_told_after_the_hal_is_closed(hal: SimulatedHal) -> None:
    controller = _controller(hal)
    hal.lines[17].stick(False)
    with pytest.raises(PrimumError):
        controller.set_output("led", True)
    hal.lines[17].stick(None)

    hal.close()

    assert controller.state().outputs[0] == OutputState("led", on=False, level=0)


def _unsure_led_whose_reads_fail(hal: SimulatedHal) -> Controller:
    """The LED did not follow a command, and then its line cannot even be read."""
    controller = _controller(hal)
    hal.lines[17].stick(False)
    with pytest.raises(PrimumError):
        controller.set_output("led", True)
    hal.lines[17].fail_reads(OSError(5, "I/O error"))
    return controller


def test_a_level_that_cannot_be_read_does_not_break_the_state(
    hal: SimulatedHal, caplog: pytest.LogCaptureFixture
) -> None:
    controller = _unsure_led_whose_reads_fail(hal)

    state = controller.state()

    assert state.outputs[0] == OutputState("led", on=True, level=100)  # what was written
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
        controller.set_output("led", True)
    readings = iter([True, False])
    hal.lines[17].read = lambda: next(readings)  # type: ignore[method-assign]  # a line that flickers

    assert controller.state().outputs[0] == OutputState("led", on=True, level=100)
