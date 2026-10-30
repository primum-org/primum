import pytest

from primum_runtime.control import Controller, OutputState, State
from primum_runtime.errors import PrimumError
from primum_runtime.hal import OutputSpec, SimulatedHal

SPECS = {"led": OutputSpec(pin=17), "lamp": OutputSpec(pin=27)}


@pytest.fixture
def hal() -> SimulatedHal:
    return SimulatedHal()


def test_outputs_start_off_in_configuration_order(hal: SimulatedHal) -> None:
    controller = Controller(hal, SPECS)

    assert controller.state() == State(
        (OutputState("led", on=False), OutputState("lamp", on=False)), panic=False
    )


def test_set_output_drives_the_line_and_notifies_the_new_state(hal: SimulatedHal) -> None:
    controller = Controller(hal, SPECS)
    states: list[State] = []
    controller.subscribe(states.append)

    controller.set_output("led", True)

    assert hal.lines[17].active
    assert states == [controller.state()]
    assert states[0].outputs[0] == OutputState("led", on=True)


def test_unknown_output_raises_output_unknown(hal: SimulatedHal) -> None:
    controller = Controller(hal, SPECS)

    with pytest.raises(PrimumError) as raised:
        controller.set_output("fan", True)

    assert raised.value.code == "output.unknown"
    assert raised.value.params == {"name": "fan"}


def test_panic_turns_every_output_off_and_refuses_commands(hal: SimulatedHal) -> None:
    controller = Controller(hal, SPECS)
    controller.set_output("led", True)

    controller.panic()

    assert not hal.lines[17].active
    assert controller.state().panic
    with pytest.raises(PrimumError) as raised:
        controller.set_output("led", True)
    assert raised.value.code == "panic.active"
    assert not hal.lines[17].active


def test_release_panic_accepts_commands_again_with_outputs_still_off(hal: SimulatedHal) -> None:
    controller = Controller(hal, SPECS)
    controller.panic()

    controller.release_panic()
    state_after_release = controller.state()
    controller.set_output("led", True)

    assert not state_after_release.panic
    assert not any(output.on for output in state_after_release.outputs)
    assert hal.lines[17].active


def test_panic_stays_latched_and_notified_when_the_safe_state_fails(hal: SimulatedHal) -> None:
    controller = Controller(hal, SPECS)
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
    controller = Controller(hal, SPECS)
    states: list[State] = []
    unsubscribe = controller.subscribe(states.append)

    unsubscribe()
    controller.set_output("led", True)

    assert states == []
