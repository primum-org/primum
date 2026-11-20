"""The timer that wakes the controller when a test is due, with a scheduler moved by hand."""

from collections.abc import Callable

import pytest

from primum_runtime.api.expiry import ExpiryTimer
from primum_runtime.board import load_board, load_profile, option_limits
from primum_runtime.control import Controller
from primum_runtime.drivers import ElementConfig, load_manifests
from primum_runtime.hal import SimulatedHal

BOARD = load_board("rpi4b")
ELEMENTS = (
    ElementConfig("led", "digital_output", 17, active_low=False),
    ElementConfig("lamp", "digital_output", 27, active_low=False),
)


class Call:
    def __init__(self, delay_s: float, callback: Callable[[], None]) -> None:
        self.delay_s = delay_s
        self.callback = callback
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class Loop:
    """Stands in for the event loop: remembers what it was asked to call later, and a test
    runs the pending call when it decides that time has passed."""

    def __init__(self) -> None:
        self.now = 100.0
        self.calls: list[Call] = []

    def clock(self) -> float:
        return self.now

    def call_later(self, delay_s: float, callback: Callable[[], None]) -> Call:
        self.calls.append(Call(delay_s, callback))
        return self.calls[-1]

    def pending(self) -> list[Call]:
        return [call for call in self.calls if not call.cancelled]

    def run(self, after_s: float) -> None:
        """Let ``after_s`` pass and run the one pending call."""
        (call,) = self.pending()
        self.now += after_s
        call.cancelled = True  # it has run: no longer pending
        call.callback()


@pytest.fixture
def loop() -> Loop:
    return Loop()


@pytest.fixture
def hal() -> SimulatedHal:
    return SimulatedHal(BOARD)


@pytest.fixture
def controller(hal: SimulatedHal, loop: Loop) -> Controller:
    limits = option_limits(load_profile("rpi4b"))
    controller = Controller(hal, ELEMENTS, load_manifests(), limits, clock=loop.clock)
    ExpiryTimer(controller, loop.call_later)
    return controller


def test_with_no_test_under_way_nothing_is_scheduled(controller: Controller, loop: Loop) -> None:
    controller.command("led", "on")

    assert loop.pending() == []


def test_a_test_schedules_its_expiry_and_the_timer_carries_it_out(
    controller: Controller, loop: Loop, hal: SimulatedHal
) -> None:
    controller.command("led", "on", duration_ms=10_000)
    assert [call.delay_s for call in loop.pending()] == [10.0]

    loop.run(after_s=10)

    assert not hal.lines[17].active
    assert loop.pending() == []


def test_the_timer_is_always_for_the_next_test_to_expire(
    controller: Controller, loop: Loop, hal: SimulatedHal
) -> None:
    controller.command("led", "on", duration_ms=10_000)
    controller.command("lamp", "on", duration_ms=3_000)
    assert [call.delay_s for call in loop.pending()] == [3.0]

    loop.run(after_s=3)

    assert [line.active for line in (hal.lines[17], hal.lines[27])] == [True, False]
    assert [call.delay_s for call in loop.pending()] == [7.0]


def test_a_command_that_ends_the_test_cancels_its_timer(controller: Controller, loop: Loop) -> None:
    controller.command("led", "on", duration_ms=10_000)

    controller.command("led", "off")

    assert loop.pending() == []


def test_panic_cancels_the_timers(controller: Controller, loop: Loop) -> None:
    controller.command("led", "on", duration_ms=10_000)

    controller.panic()

    assert loop.pending() == []


def test_a_timer_that_fires_a_moment_early_is_armed_again_for_what_is_left(
    controller: Controller, loop: Loop, hal: SimulatedHal
) -> None:
    controller.command("led", "on", duration_ms=10_000)

    loop.run(after_s=9.75)

    assert hal.lines[17].active
    assert [call.delay_s for call in loop.pending()] == [0.25]


def test_closing_it_cancels_what_was_scheduled(hal: SimulatedHal, loop: Loop) -> None:
    limits = option_limits(load_profile("rpi4b"))
    controller = Controller(hal, ELEMENTS, load_manifests(), limits, clock=loop.clock)
    timer = ExpiryTimer(controller, loop.call_later)
    controller.command("led", "on", duration_ms=10_000)

    timer.close()
    controller.command("lamp", "on", duration_ms=10_000)

    assert loop.pending() == []
