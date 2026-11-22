"""Events and automations on a board: an input or the API makes something happen, and the
automations of the package act (decision 0029). On the simulated HAL, clock moved by hand."""

from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from primum_core.generated.model import Package, PackageAction
from primum_runtime.engine import Engine
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.package import check_against_board
from show_service import (
    MANIFESTS,
    Service,
    compiled,
    make_file,
    make_id,
    make_sequence,
    package,
    running,
)

LED, BUTTON = make_id(4), make_id(6)
LED_PIN, BUTTON_PIN = 17, 27
BLINK, ON = make_id(20), make_id(30)
VISITS, PAUSED, DIVISOR = make_id(61), make_id(62), make_id(63)
PRESSED, RELEASED, GO, CALL = (make_id(number) for number in (200, 201, 202, 203))
WELCOME, FULL, LEAVE, RESET, RISKY, OFF = (make_id(number) for number in range(300, 306))
MAX_VISITS = 3


def _event(number: int, name: str, source: str, trigger: str | None = None) -> bytes:
    listened = {} if trigger is None else {"element": BUTTON, "trigger": trigger}
    return make_file("event", number, name=name, source=source, **listened)


def _automation(number: int, name: str, when: str, *do: dict[str, object], **more: object) -> bytes:
    return make_file("automation", number, name=name, when=[when], do=list(do), **more)


def _document() -> dict[str, object]:
    """A Pi with an LED and a button, a counter of visits and six automations:

    - *Welcome*: the button pressed, if there is room (``visits < max_visits``) and it is
      not paused: start *On* and count the visit;
    - *Full*: the button pressed with no room left: stop *On*;
    - *Leave*: the button released: stop *On*;
    - *Reset*: the event *Go* (of the app): no visits;
    - *Risky*: the event *Call* (of the API), if ``10 / divisor > 1``: two visits more;
    - *Off*: disabled; it would start *Blink* on *Go*.
    """
    board = {"id": make_id(3), "name": "Pi", "model": "rpi4b"}
    wired = {"board": make_id(3)}
    button = {"id": BUTTON, "name": "Button", "type": "digital_input", "pin": BUTTON_PIN}
    elements = [
        {"id": LED, "name": "LED", "type": "digital_output", "pin": LED_PIN, **wired},
        {**button, "config": [{"name": "pull", "value": "up"}], **wired},
    ]
    integer = {"type": "integer", "initial": 0, "min": 0, "setting": True}
    variables = [
        {"id": VISITS, "name": "visits", **integer, "max": MAX_VISITS},
        {"id": PAUSED, "name": "paused", "type": "boolean", "initial": False, "setting": True},
        {"id": DIVISOR, "name": "divisor", **integer, "initial": 1, "max": 10},
    ]
    constants = [{"id": make_id(64), "name": "max_visits", "type": "integer", "value": MAX_VISITS}]
    count: dict[str, object] = {"action": "increment_variable", "variable": "visits"}
    files = {
        "project.json": make_file("project", 1, name="Automations"),
        "hardware.hw": make_file("hardware", 2, boards=[board], elements=elements),
        "shop.vars": make_file("variables", 60, constants=constants, variables=variables),
        "blink.sec": make_sequence(
            20, "Blink", 4, {"atMs": 1000, "durationMs": 1000, "action": "on"}
        ),
        "on.sec": make_sequence(
            30, "On", 4, {"atMs": 0, "durationMs": 0, "action": "on"}, whenDone="hold"
        ),
        "pressed.evt": _event(200, "Pressed", "element", "on"),
        "released.evt": _event(201, "Released", "element", "off"),
        "go.evt": _event(202, "Go", "ui"),
        "call.evt": _event(203, "Call", "api"),
        "welcome.auto": _automation(
            300,
            "Welcome",
            PRESSED,
            {"action": "start_sequence", "sequence": ON},
            count,
            **{"if": "visits < max_visits and not paused"},
        ),
        "full.auto": _automation(
            301,
            "Full",
            PRESSED,
            {"action": "stop_sequence", "sequence": ON},
            **{"if": "visits >= max_visits"},
        ),
        "leave.auto": _automation(
            302, "Leave", RELEASED, {"action": "stop_sequence", "sequence": ON}
        ),
        "reset.auto": _automation(
            303, "Reset", GO, {"action": "set_variable", "variable": "visits", "value": 0}
        ),
        "risky.auto": _automation(
            304, "Risky", CALL, {**count, "value": 2}, **{"if": "10 / divisor > 1"}
        ),
        "off.auto": _automation(
            305, "Off", GO, {"action": "start_sequence", "sequence": BLINK}, enabled=False
        ),
    }
    return compiled(files)


DOCUMENT = _document()


class _Shop(Service):
    def __init__(self, loaded: Package | None = None) -> None:
        super().__init__(package(DOCUMENT) if loaded is None else loaded)

    def press(self, pressed: bool = True) -> None:
        """The button changes, and the service reads it, as its loop would."""
        self.hal.simulate_input(BUTTON_PIN, pressed)
        self.controller.read_inputs()

    def value(self, variable: str = VISITS) -> object:
        return next(v.value for v in self.controller.state().variables if v.id == variable)

    def problem(self, automation: str) -> PrimumError | None:
        return next(a.problem for a in self.controller.state().automations if a.id == automation)


@pytest.fixture
def shop() -> _Shop:
    return _Shop()


def test_an_input_that_turns_on_starts_what_its_automation_says(shop: _Shop) -> None:
    shop.press()

    assert (shop.led, shop.running(), shop.value()) == (True, ["On"], 1)
    assert shop.by(LED) == "sequence"


def test_an_input_that_turns_off_is_another_event(shop: _Shop) -> None:
    shop.press()

    shop.press(False)

    assert (shop.led, shop.running(), shop.value()) == (False, [], 1)


def test_a_sequence_started_by_an_input_runs_its_time_and_ends() -> None:
    """Sensor, sequence, rest: what the phase is for, on the simulated board."""
    loaded = package(DOCUMENT)
    welcome = next(a for a in loaded.automations if a.name == "Welcome")
    blink = PackageAction(action="start_sequence", sequence=UUID(BLINK))
    shop = _Shop(replace(loaded, automations=(replace(welcome, if_=(), do=(blink,)),)))

    shop.press()
    started = (shop.led, shop.running(), shop.controller.next_expiry_s())
    shop.after(1)
    during = shop.led
    shop.after(1)

    assert started == (False, ["Blink"], 1.0)  # its clip starts a second in: the timer knows
    assert during is True
    assert (shop.led, shop.running()) == (False, [])


def test_every_condition_is_worked_out_before_any_automation_acts(shop: _Shop) -> None:
    """The third visit fills the shop. *Full* waits for the same press and holds once
    there are three, but it is judged on the two there were: it acts on the next press."""
    for _ in range(MAX_VISITS):
        shop.press()
        shop.press(False)
    shop.press()
    third = (shop.running(), shop.value())
    shop.press(False)

    shop.controller.start_sequence(ON)
    shop.press()

    assert third == ([], MAX_VISITS)  # no room: Welcome did not act, Full stopped nothing new
    assert shop.running() == []  # Full stopped On


def test_the_third_press_still_welcomes(shop: _Shop) -> None:
    for _ in range(MAX_VISITS - 1):
        shop.press()
        shop.press(False)

    shop.press()

    assert (shop.running(), shop.value()) == (["On"], MAX_VISITS)


def test_an_increment_stops_at_the_limit_of_its_variable(shop: _Shop) -> None:
    counted: list[object] = []
    for _ in range(3):
        shop.controller.fire_event(CALL)
        counted.append(shop.value())

    assert counted == [2, MAX_VISITS, MAX_VISITS]
    assert [type(count) for count in counted] == [int, int, int]  # 3, never 3.0


def test_an_action_sets_a_variable(shop: _Shop) -> None:
    shop.press()

    shop.controller.fire_event(GO)

    assert shop.value() == 0


def test_a_disabled_automation_does_not_act(shop: _Shop) -> None:
    shop.controller.fire_event(GO)

    assert shop.running() == []


def test_a_condition_reads_the_values_the_variables_have_now(shop: _Shop) -> None:
    shop.controller.set_variable(PAUSED, True)

    shop.press()

    assert (shop.led, shop.value()) == (False, 0)


def test_while_panic_is_on_what_happens_starts_nothing_and_is_not_kept(shop: _Shop) -> None:
    shop.controller.panic()

    shop.press()
    during = (shop.led, shop.running(), shop.value())
    shop.controller.release_panic()
    shop.after(1)

    assert during == (False, [], 0)
    assert (shop.led, shop.running(), shop.value()) == (False, [], 0)
    assert shop.controller.state().inputs[0].active  # the input itself is still read


def test_an_event_cannot_be_fired_while_panic_is_on(shop: _Shop) -> None:
    shop.controller.panic()

    with pytest.raises(PrimumError) as refused:
        shop.controller.fire_event(CALL)

    assert refused.value.code is ErrorCode.PANIC_ACTIVE
    assert shop.value() == 0


def test_an_event_of_an_element_is_never_fired_by_hand(shop: _Shop) -> None:
    with pytest.raises(PrimumError) as refused:
        shop.controller.fire_event(PRESSED)

    assert (refused.value.code, dict(refused.value.params)) == (
        ErrorCode.EVENT_NOT_FIREABLE,
        {"id": PRESSED, "name": "Pressed"},
    )
    assert (shop.led, shop.value()) == (False, 0)


@pytest.mark.parametrize("event", [make_id(999), "not an id", ON])
def test_an_event_the_package_does_not_have_is_unknown(shop: _Shop, event: str) -> None:
    with pytest.raises(PrimumError) as refused:
        shop.controller.fire_event(event)

    assert (refused.value.code, dict(refused.value.params)) == (
        ErrorCode.EVENT_UNKNOWN,
        {"id": event},
    )


def test_a_condition_that_cannot_be_worked_out_does_nothing_and_is_told(
    shop: _Shop, caplog: pytest.LogCaptureFixture
) -> None:
    shop.controller.set_variable(DIVISOR, 0)

    shop.controller.fire_event(CALL)

    problem = shop.problem(RISKY)
    assert shop.value() == 0
    assert problem is not None
    assert (problem.code, dict(problem.params)) == (
        ErrorCode.AUTOMATION_CONDITION_FAILED,
        {"automation": "Risky", "reason": "division_by_zero"},
    )
    assert "automation.condition_failed" in caplog.text


def test_a_problem_is_forgotten_when_the_automation_next_acts_cleanly(shop: _Shop) -> None:
    shop.controller.set_variable(DIVISOR, 0)
    shop.controller.fire_event(CALL)

    shop.controller.set_variable(DIVISOR, 5)
    shop.controller.fire_event(CALL)

    assert (shop.problem(RISKY), shop.value()) == (None, 2)


def test_a_problem_is_forgotten_when_the_condition_is_next_worked_out_even_if_false(
    shop: _Shop,
) -> None:
    """Nothing went wrong the second time: the condition was worked out, and it was false."""
    shop.controller.set_variable(DIVISOR, 0)
    shop.controller.fire_event(CALL)
    failed = shop.problem(RISKY)

    shop.controller.set_variable(DIVISOR, 10)  # 10 / 10 > 1 is false
    shop.controller.fire_event(CALL)

    assert failed is not None
    assert (shop.problem(RISKY), shop.value()) == (None, 0)


def test_a_problem_stays_while_other_events_happen(shop: _Shop) -> None:
    shop.controller.set_variable(DIVISOR, 0)
    shop.controller.fire_event(CALL)

    shop.controller.fire_event(GO)  # not an event Risky waits for

    assert shop.problem(RISKY) is not None


def test_an_event_that_cannot_be_dealt_with_does_not_stop_the_inputs(
    shop: _Shop, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Whatever goes wrong judging one event, the next is still read and dealt with: the
    loop of the service stops listening to the inputs on anything this lets through."""

    def broken(*_: object) -> None:
        raise RuntimeError("unexpected")

    with monkeypatch.context() as patched:
        patched.setattr("primum_runtime.control.verdicts", broken)
        shop.press()
    pressed = shop.controller.state().inputs[0].active
    shop.press(False)
    shop.press()

    assert pressed  # the input itself was read
    assert "Pressed" in caplog.text
    assert (shop.led, shop.value()) == (True, 1)  # the press after it is an event as any


def test_an_action_that_fails_is_logged_once(
    shop: _Shop, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(*_: object) -> None:
        raise PrimumError(ErrorCode.SEQUENCE_UNKNOWN, {"id": ON})

    monkeypatch.setattr(Engine, "start", broken)

    shop.press()

    told = [record.levelname for record in caplog.records if "Welcome" in record.message]
    assert told == ["ERROR"]  # once, with the traceback


def test_an_action_that_fails_does_not_stop_the_ones_after_it(
    shop: _Shop, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(*_: object) -> None:
        raise PrimumError(ErrorCode.SEQUENCE_UNKNOWN, {"id": ON})

    monkeypatch.setattr(Engine, "start", broken)

    shop.press()

    problem = shop.problem(WELCOME)
    assert shop.value() == 1  # the count, after the start that failed
    assert problem is not None
    assert (problem.code, dict(problem.params)) == (
        ErrorCode.AUTOMATION_ACTION_FAILED,
        {"automation": "Welcome", "action": "start_sequence", "problem": "sequence.unknown"},
    )
    assert "start_sequence failed" in caplog.text


def test_lost_changes_of_an_input_are_told_in_its_state(shop: _Shop) -> None:
    for number in range(7):
        shop.hal.simulate_input(BUTTON_PIN, number % 2 == 0)
    shop.hal.lose_events(4)

    shop.controller.read_inputs()

    assert shop.controller.state().inputs[0].lost_events == 4


def test_listeners_are_told_once_per_reading_of_the_inputs(shop: _Shop) -> None:
    shop.states.clear()

    shop.press()

    [state] = shop.states
    assert [s.name for s in state.sequences if s.running] == ["On"]
    assert next(v.value for v in state.variables if v.id == VISITS) == 1


def test_a_package_whose_event_listens_to_an_output_is_refused() -> None:
    loaded = package(DOCUMENT)
    pressed = next(event for event in loaded.events if event.name == "Pressed")
    listening = replace(pressed, element=UUID(LED))

    with pytest.raises(PrimumError) as refused:
        check_against_board(replace(loaded, events=(listening,)), MANIFESTS)

    assert refused.value.code is ErrorCode.EVENT_NOT_LISTENABLE
    assert dict(refused.value.params) == {
        "event": listening.name,
        "element": "LED",
        "trigger": listening.trigger,
        "available": (),
        "id": LED,
    }


# --- the API -------------------------------------------------------------------------------


def test_the_api_fires_an_event_and_answers_with_the_new_state(tmp_path: Path) -> None:
    with running(tmp_path, DOCUMENT) as (client, _):
        client.post(f"/api/events/{CALL}/fire")
        answer = client.post(f"/api/events/{CALL}/fire")

    assert answer.status_code == 200
    visits = next(v["value"] for v in answer.json()["variables"] if v["id"] == VISITS)
    assert (visits, type(visits)) == (3, int)  # at its limit, and still a whole number
    assert '"value":3,' in answer.text.replace(" ", "")


def test_the_status_lists_the_events_and_the_automations(tmp_path: Path) -> None:
    with running(tmp_path, DOCUMENT) as (client, _):
        client.put(f"/api/variables/{DIVISOR}", json={"value": 0})
        client.post(f"/api/events/{CALL}/fire")
        state = client.get("/api/status").json()

    assert {(event["name"], event["source"]) for event in state["events"]} == {
        ("Pressed", "element"),
        ("Released", "element"),
        ("Go", "ui"),
        ("Call", "api"),
    }
    by_name = {automation["name"]: automation for automation in state["automations"]}
    assert (by_name["Off"]["enabled"], by_name["Welcome"]["enabled"]) == (False, True)
    assert by_name["Welcome"]["problem"] is None
    assert by_name["Risky"]["problem"] == {
        "code": "automation.condition_failed",
        "params": {"automation": "Risky", "reason": "division_by_zero"},
    }


@pytest.mark.parametrize(
    ("event", "status", "code"),
    [
        (make_id(999), 404, "event.unknown"),
        (PRESSED, 409, "event.not_fireable"),
    ],
)
def test_the_api_refuses_an_event_it_cannot_fire(
    tmp_path: Path, event: str, status: int, code: str
) -> None:
    with running(tmp_path, DOCUMENT) as (client, _):
        answer = client.post(f"/api/events/{event}/fire")

    assert (answer.status_code, answer.json()["code"]) == (status, code)


def test_the_api_refuses_to_fire_an_event_while_panic_is_on(tmp_path: Path) -> None:
    with running(tmp_path, DOCUMENT) as (client, _):
        client.post("/api/panic")
        answer = client.post(f"/api/events/{CALL}/fire")

    assert (answer.status_code, answer.json()["code"]) == (409, "panic.active")


def test_an_input_of_a_running_service_starts_its_sequence(tmp_path: Path) -> None:
    """The whole way: the line of the button changes, the loop of the service reads it, the
    automation starts the sequence and the LED goes on."""
    with running(tmp_path, DOCUMENT) as (client, hal), client.websocket_connect("/api/ws") as ws:
        ws.receive_json()
        hal.simulate_input(BUTTON_PIN, True)
        state = ws.receive_json()
        lit = hal.lines[LED_PIN].active  # before the service stops and makes it safe

    assert lit
    assert [s["name"] for s in state["sequences"] if s["running"]] == ["On"]
