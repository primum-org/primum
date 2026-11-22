"""Fades moved in time and variables read while running, on the show of ``show_service``: the
simulated board, a clock moved by hand."""

from collections.abc import Callable, Iterator, Mapping
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from primum_core.values import Value
from primum_runtime.api.expiry import ExpiryTimer
from primum_runtime.control import FADE_STEP_S, FADE_TOLD_S, RETRY_REST_S
from primum_runtime.drivers import PwmOutputDriver
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.hal import SimulatedHal
from show_service import (
    BRIGHTNESS,
    DOWN,
    GLOW,
    HIGH,
    LAMP,
    LAMP_PIN,
    LED,
    LOW,
    ON,
    PULSE,
    RISE,
    SLOW_PULSE,
    SPEED,
    UNKNOWN,
    Service,
    running,
)

STEPS_PER_S = round(1 / FADE_STEP_S)


@pytest.fixture
def service() -> Service:
    return Service()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, SimulatedHal]]:
    with running(tmp_path) as service:
        yield service


def _lamp(service: Service) -> float:
    """The lamp's level, from 0 to 100, as the board has it."""
    return round(service.lamp * 100, 3)


def _brightness(service: Service) -> object:
    return service.controller.state().variables[0].value


def test_a_fade_moves_its_output_in_proportion_to_the_time_gone_by(service: Service) -> None:
    service.controller.start_sequence(GLOW)
    levels = [_lamp(service)]

    for _ in range(4):
        service.after(0.5)
        levels.append(_lamp(service))

    assert levels == [20, 35, 50, 65, 80]


def test_a_fade_is_stepped_while_it_moves_and_not_after(service: Service) -> None:
    service.controller.start_sequence(GLOW)
    moving = service.controller.next_expiry_s()

    service.after(1.99)
    nearly = service.controller.next_expiry_s()
    service.after(0.01)

    assert moving == pytest.approx(FADE_STEP_S)
    assert nearly == pytest.approx(0.01)  # its end comes before the next step
    assert service.controller.next_expiry_s() is None  # held at 80: nothing left to do
    assert _lamp(service) == 80


def test_every_step_writes_the_level_its_time_asks_for(service: Service) -> None:
    service.controller.start_sequence(GLOW)

    for _ in range(STEPS_PER_S):
        service.after(FADE_STEP_S)

    written = service.hal.pwm_lines[LAMP_PIN].history
    assert len(written) == STEPS_PER_S + 1  # where it starts, then one per step
    assert list(written) == sorted(written)
    assert written[-1] == pytest.approx(0.5)


def test_a_wake_that_comes_late_goes_to_where_the_fade_is_by_then(service: Service) -> None:
    service.controller.start_sequence(GLOW)

    service.after(1.5)

    assert _lamp(service) == 65


def test_listeners_are_told_of_a_fade_now_and_then_and_when_it_ends(service: Service) -> None:
    service.controller.start_sequence(GLOW)
    told = len(service.states)

    for _ in range(2 * STEPS_PER_S):
        service.after(FADE_STEP_S)

    during = len(service.states) - told
    assert 2 / FADE_TOLD_S - 2 <= during <= 2 / FADE_TOLD_S + 1  # not once per step
    assert service.states[-1].outputs[1].level == 80


def test_a_fade_without_its_from_starts_from_where_the_output_is(service: Service) -> None:
    service.controller.start_sequence(GLOW)
    service.after(2)  # held at 80

    service.controller.start_sequence(DOWN)
    start = _lamp(service)
    service.after(0.5)

    assert (start, _lamp(service)) == (80, 40)


def test_a_fade_goes_on_under_a_person_s_hand_from_the_level_it_found(service: Service) -> None:
    """Held by hand at 60, the fade to 0 starts from 60, unseen; let go half way, the lamp
    is where the fade is by then."""
    service.controller.command(LAMP, "set", {"level": 60})

    service.controller.start_sequence(DOWN)
    held = (_lamp(service), service.controller.next_expiry_s())
    service.clock.now += 0.5
    service.controller.release(LAMP)

    assert held == (60, 1.0)  # nothing to step while a person holds it: only its end
    assert _lamp(service) == 30


def test_a_variable_is_read_when_its_command_starts_and_kept_while_it_lasts(
    service: Service,
) -> None:
    service.controller.set_variable(BRIGHTNESS, 40)
    service.controller.start_sequence(RISE)
    service.after(0.5)
    half = _lamp(service)

    service.controller.set_variable(BRIGHTNESS, 90)
    service.after(0.5)
    kept = _lamp(service)
    service.controller.start_sequence(RISE)  # again: a new command, which reads 90
    service.after(1)

    assert (half, kept, _lamp(service)) == (20, 40, 90)


def test_setting_a_variable_tells_the_listeners_its_new_value(service: Service) -> None:
    service.controller.set_variable(BRIGHTNESS, 75)

    variable = service.states[-1].variables[0]
    assert (variable.id, variable.name, variable.type, variable.value) == (
        BRIGHTNESS,
        "brightness",
        "integer",
        75,
    )
    assert (variable.min, variable.max, variable.setting) == (0, 100, True)


@pytest.mark.parametrize(
    ("variable", "value", "code", "params"),
    [
        (UNKNOWN, 5, ErrorCode.VARIABLE_UNKNOWN, {"id": UNKNOWN}),
        ("brightness", 5, ErrorCode.VARIABLE_UNKNOWN, {"id": "brightness"}),
        (BRIGHTNESS, "high", ErrorCode.VARIABLE_VALUE_INVALID, None),
        (BRIGHTNESS, True, ErrorCode.VARIABLE_VALUE_INVALID, None),
        (BRIGHTNESS, 2.5, ErrorCode.VARIABLE_VALUE_INVALID, None),
        (BRIGHTNESS, 101, ErrorCode.VARIABLE_VALUE_OUT_OF_RANGE, None),
        (BRIGHTNESS, -1, ErrorCode.VARIABLE_VALUE_OUT_OF_RANGE, None),
    ],
)
def test_a_value_a_variable_cannot_hold_is_refused_and_changes_nothing(
    service: Service,
    variable: str,
    value: float | bool | str,
    code: ErrorCode,
    params: dict[str, object] | None,
) -> None:
    told = len(service.states)
    expected = params
    if code is ErrorCode.VARIABLE_VALUE_INVALID:
        expected = {"name": "brightness", "type": "integer"}
    if code is ErrorCode.VARIABLE_VALUE_OUT_OF_RANGE:
        expected = {"name": "brightness", "value": value, "min": 0, "max": 100}

    with pytest.raises(PrimumError) as refused:
        service.controller.set_variable(variable, value)

    assert (refused.value.code, dict(refused.value.params)) == (code, expected)
    assert _brightness(service) == 60
    assert len(service.states) == told


def test_panic_stops_a_fade_where_it_rests(service: Service) -> None:
    service.controller.start_sequence(GLOW)
    service.after(1)

    service.controller.panic()

    assert _lamp(service) == 0
    assert service.controller.next_expiry_s() is None


def test_a_fade_and_a_digital_output_run_side_by_side(service: Service) -> None:
    service.controller.start_sequence(ON)
    service.controller.start_sequence(GLOW)

    service.after(1)

    assert (service.led, _lamp(service)) == (True, 50)
    assert service.hal.lines[17].history == (True,)  # written once, however many steps


# --- over the API --------------------------------------------------------------------------


def test_a_variable_is_set_over_the_api(client: tuple[TestClient, SimulatedHal]) -> None:
    api, _ = client

    response = api.put(f"/api/variables/{BRIGHTNESS}", json={"value": 30})

    assert response.status_code == 200
    assert response.json()["variables"][:1] == [
        {
            "id": BRIGHTNESS,
            "name": "brightness",
            "type": "integer",
            "value": 30,
            "min": 0,
            "max": 100,
            "setting": True,
            "persistent": False,
        }
    ]


def test_a_value_a_variable_cannot_hold_is_a_422_and_one_that_is_not_there_a_404(
    client: tuple[TestClient, SimulatedHal],
) -> None:
    api, _ = client

    too_much = api.put(f"/api/variables/{BRIGHTNESS}", json={"value": 500})
    wrong = api.put(f"/api/variables/{BRIGHTNESS}", json={"value": "high"})
    nothing = api.put(f"/api/variables/{UNKNOWN}", json={"value": 5})

    assert (too_much.status_code, too_much.json()["code"]) == (422, "variable.value_out_of_range")
    assert (wrong.status_code, wrong.json()["code"]) == (422, "variable.value_invalid")
    assert (nothing.status_code, nothing.json()["code"]) == (404, "variable.unknown")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_a_value_that_is_no_number_is_refused(service: Service, value: float) -> None:
    """NaN is neither under a minimum nor over a maximum: it passed the limits, and every
    command that then read the variable failed."""
    with pytest.raises(PrimumError) as refused:
        service.controller.set_variable(SPEED, value)

    assert (refused.value.code, dict(refused.value.params)) == (
        ErrorCode.VARIABLE_VALUE_INVALID,
        {"name": "speed", "type": "number"},
    )
    assert service.controller.state().variables[1].value == 1.5


def test_a_value_that_is_no_number_is_a_422_over_the_api(
    client: tuple[TestClient, SimulatedHal],
) -> None:
    api, _ = client

    for written in ("NaN", "Infinity", "-Infinity"):
        response = api.put(
            f"/api/variables/{SPEED}",
            content='{"value": ' + written + "}",
            headers={"Content-Type": "application/json"},
        )
        assert (response.status_code, response.json()["code"]) == (
            422,
            "variable.value_invalid",
        ), written


def _break_fades_of_the_lamp(monkeypatch: pytest.MonkeyPatch) -> None:
    """From now on what a fade asks of a PWM output cannot be worked out, as when a value it
    reads is one its driver refuses."""
    level_for = PwmOutputDriver.level_for

    def refusing(
        driver: PwmOutputDriver, action: str, arguments: Mapping[str, Value] | None = None
    ) -> float:
        if action == "fade":
            raise PrimumError(ErrorCode.ELEMENT_VALUE_OUT_OF_RANGE, {"element": driver.name})
        return level_for(driver, action, arguments)

    monkeypatch.setattr(PwmOutputDriver, "level_for", refusing)


def test_a_command_that_cannot_be_worked_out_does_not_stop_the_other_outputs(
    service: Service, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What a sequence asks of the lamp fails to be worked out: the lamp says it is not
    where it should be, and everything else goes on: the sequence starts, a test of the LED
    expires, the LED is released, the timer is told when to come back."""
    _break_fades_of_the_lamp(monkeypatch)

    service.controller.start_sequence(RISE)
    failed = {output.id: output.rest_failed for output in service.controller.state().outputs}
    service.controller.command(LED, "on", duration_ms=1000)
    waiting = service.controller.next_expiry_s()
    service.after(1)
    expired = service.led
    service.controller.command(LED, "on")
    service.controller.release(LED)

    assert failed == {LED: False, LAMP: True}
    assert waiting == pytest.approx(1.0)
    assert (expired, service.led) == (False, False)
    assert service.running() == ["Rise"]


def test_an_output_whose_command_can_be_worked_out_again_gets_there(
    service: Service, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as broken:
        _break_fades_of_the_lamp(broken)
        service.controller.start_sequence(RISE)

    service.after(RETRY_REST_S)

    assert _lamp(service) == 60  # the fade is over by now: where it ends
    assert not service.controller.state().outputs[1].rest_failed


@pytest.mark.parametrize(
    ("sequence", "half_s", "late_s"),
    [(PULSE, 0.1, 0.0), (PULSE, 0.1, 0.005), (SLOW_PULSE, 1.0, 0.0), (SLOW_PULSE, 1.0, 0.013)],
    ids=["100 ms", "100 ms, every step 5 ms late", "1 s", "1 s, every step 13 ms late"],
)
def test_a_fade_that_follows_another_starts_from_where_that_one_ends(
    service: Service, sequence: str, half_s: float, late_s: float
) -> None:
    """Up to 100, then down from where it is: the way down starts at 100, the end of the way
    up, not at the last step that happened to be written before it. So at every wake, however
    late it comes, the lamp is where a pulse from 0 to 100 and back is at that time."""
    service.controller.start_sequence(sequence)
    started = service.clock.now
    seen: list[tuple[float, float]] = []

    for _ in range(round(2 * half_s / FADE_STEP_S) + 2):
        service.after(FADE_STEP_S + late_s)
        seen.append((service.clock.now - started, _lamp(service)))

    for at_s, level in seen:
        expected = 100 * max(0.0, 1 - abs(at_s - half_s) / half_s)
        assert level == pytest.approx(expected, abs=0.2), at_s  # a PWM step is 1/20000
    if late_s == 0:
        assert max(service.hal.pwm_lines[LAMP_PIN].history) == 1.0  # written at its instant


def test_a_fade_that_cuts_another_starts_from_where_that_one_is_by_then(
    service: Service,
) -> None:
    """*Glow* is half a second in, last written at 35. A quarter of a second later, with no
    step in between, *Down* starts: from 42.5, where *Glow* is by then, not from 35."""
    service.controller.start_sequence(GLOW)
    service.after(0.5)
    service.clock.now += 0.25

    service.controller.start_sequence(DOWN)

    assert _lamp(service) == 42.5


@pytest.mark.parametrize(("woken_at_s", "level"), [(10.0, 55.0), (10.3, 53.5)])
def test_a_fade_that_starts_under_a_higher_priority_starts_from_what_it_is_handed(
    service: Service, woken_at_s: float, level: float
) -> None:
    """*High* fades the lamp up for ten seconds. *Low*, a fade to 0 in twenty seconds from
    where the lamp is, starts a second in and gets the lamp when *High* ends: at 100, where
    *High* left it, not at the 10 it was at when *Low* started. By then nine of its twenty
    seconds have gone: 55. Woken late, it is further along, still from 100."""
    service.controller.start_sequence(HIGH)
    service.after(1)
    service.controller.start_sequence(LOW)
    service.after(8.5)
    under = (_lamp(service), service.running())

    service.after(woken_at_s - 9.5)

    assert under == (95, ["High", "Low"])
    assert _lamp(service) == pytest.approx(level)


class Scheduler:
    """Stands in for the event loop under ``ExpiryTimer``: one call later, by the clock of the
    service, run when a test lets that much time pass."""

    def __init__(self, service: Service) -> None:
        self._service = service
        self._due: tuple[float, Callable[[], None]] | None = None

    def call_later(self, delay_s: float, callback: Callable[[], None]) -> "Scheduler":
        self._due = (self._service.clock.now + delay_s, callback)
        return self

    def cancel(self) -> None:
        self._due = None

    def let_pass(self, seconds: float) -> None:
        self._service.clock.now += seconds
        # A whisker of slack: the clock is a float, and a step is not due "almost".
        if self._due is not None and self._due[0] <= self._service.clock.now + 1e-9:
            _, callback = self._due
            self._due = None
            callback()


def test_a_fade_keeps_its_steps_while_the_state_changes_for_other_reasons(
    service: Service,
) -> None:
    """Something tells the listeners every 5 ms (a variable set, here; inputs and automations
    later), and each time the timer is armed again. The next step is due 20 ms after the
    last one, not 20 ms after whoever asked last: the fade must not wait for silence."""
    scheduler = Scheduler(service)
    ExpiryTimer(service.controller, scheduler.call_later)
    service.controller.start_sequence(GLOW)

    for tick in range(200):  # a second, 5 ms at a time
        scheduler.let_pass(0.005)
        service.controller.set_variable(BRIGHTNESS, tick % 100)

    written = service.hal.pwm_lines[LAMP_PIN].history
    assert len(written) >= STEPS_PER_S  # one per step, give or take the first
    assert _lamp(service) == pytest.approx(50, abs=0.5)
