"""The trace: what the board did, and why, as it happened (decision 0032)."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from starlette.websockets import WebSocketDisconnect

from primum_runtime.engine import Engine
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.trace import Entry, Trace
from show_service import (
    BLINK,
    BRIGHTNESS,
    GLOW,
    LED,
    ON,
    OVER,
    WAIT_S,
    Service,
    compiled,
    make_file,
    make_id,
    make_sequence,
    package,
    running,
)

# --- the trace itself ------------------------------------------------------------------------


def test_entries_are_numbered_from_one_and_kept_in_order() -> None:
    trace = Trace()

    first = trace.add("panic.on", {}, 10)
    second = trace.add("panic.released", {}, 20, cause=first)

    assert (first, second) == (1, 2)
    assert [(e.number, e.kind, e.at_ms, e.cause) for e in trace.entries()] == [
        (1, "panic.on", 10, None),
        (2, "panic.released", 20, 1),
    ]


def test_entries_after_a_number_are_the_ones_that_followed_it() -> None:
    trace = Trace()
    for at in range(5):
        trace.add("panic.on", {}, at)

    assert [entry.number for entry in trace.entries(after=3)] == [4, 5]
    assert trace.entries(after=5) == ()


def test_only_the_last_entries_are_kept_and_the_numbers_go_on() -> None:
    trace = Trace(size=3)
    for at in range(5):
        trace.add("panic.on", {}, at)

    assert [entry.number for entry in trace.entries()] == [3, 4, 5]
    assert (trace.first, trace.last) == (3, 5)


def test_an_empty_trace_says_where_it_will_start() -> None:
    trace = Trace()

    assert (trace.entries(), trace.first, trace.last) == ((), 1, 0)


def test_listeners_are_told_of_each_entry_until_they_leave() -> None:
    trace = Trace()
    told: list[int] = []
    leave = trace.subscribe(lambda: told.append(trace.last))

    trace.add("panic.on", {}, 0)
    leave()
    trace.add("panic.released", {}, 1)

    assert told == [1]


def test_the_params_of_an_entry_cannot_be_changed_by_who_gave_them() -> None:
    trace = Trace()
    params: dict[str, str] = {"name": "LED"}
    trace.add("output.released", params, 0)

    params["name"] = "changed"

    assert trace.entries()[0].params == {"name": "LED"}


# --- what the controller notes ---------------------------------------------------------------


def _kinds(service: Service, after: int = 1) -> list[str]:
    """The kinds noted after the service started (its first entry)."""
    return [entry.kind for entry in service.controller.trace.entries(after)]


def _last(service: Service, kind: str) -> Entry:
    return next(e for e in reversed(service.controller.trace.entries()) if e.kind == kind)


@pytest.fixture
def service() -> Service:
    return Service()


def test_the_trace_starts_with_the_service_and_its_package(service: Service) -> None:
    [started] = service.controller.trace.entries()

    assert (started.number, started.kind, started.at_ms) == (1, "service.started", 0)
    assert started.params["project"] == "Arbiter"
    assert str(started.params["package"]).startswith("sha256:")


def test_a_sequence_is_noted_when_it_starts_and_when_it_reaches_its_end(service: Service) -> None:
    service.controller.start_sequence(BLINK)
    service.after(1)
    service.after(1)

    entries = service.controller.trace.entries(after=1)
    assert [(e.kind, e.params.get("name"), e.at_ms) for e in entries] == [
        ("sequence.started", "Blink", 0),
        ("sequence.ended", "Blink", 2000),
    ]
    assert entries[0].params["by"] == "api"


def test_a_sequence_stopped_by_a_request_says_so(service: Service) -> None:
    service.controller.start_sequence(ON)

    service.controller.stop_sequence(ON)

    stopped = _last(service, "sequence.stopped")
    assert dict(stopped.params) == {"id": ON, "name": "On", "by": "api"}


def test_stopping_a_sequence_that_is_not_running_notes_nothing(service: Service) -> None:
    service.controller.stop_sequence(ON)

    assert _kinds(service) == []


def test_a_sequence_started_while_it_runs_is_one_entry_a_restart(service: Service) -> None:
    service.controller.start_sequence(ON)
    service.clock.now += 0.5

    service.controller.start_sequence(ON)

    assert _kinds(service) == ["sequence.started", "sequence.started"]
    assert _last(service, "sequence.started").params["restarted"] is True


def test_a_sequence_that_ended_unseen_is_noted_before_what_comes_next(service: Service) -> None:
    """Nobody woke the controller when Blink ended; the next request finds it gone, and it
    ended on its own, not by that request."""
    service.controller.start_sequence(BLINK)
    service.clock.now += 5

    service.controller.start_sequence(OVER)

    assert _kinds(service) == ["sequence.started", "sequence.ended", "sequence.started"]


def test_what_a_person_asks_of_an_output_is_noted(service: Service) -> None:
    service.controller.command(LED, "on")
    service.controller.command(LED, "on", duration_ms=1000)
    service.after(1)
    service.controller.command(LED, "off")
    service.controller.release(LED)

    entries = service.controller.trace.entries(after=1)
    assert [e.kind for e in entries] == [
        "output.commanded",
        "output.commanded",
        "output.test_ended",
        "output.commanded",
        "output.released",
    ]
    assert dict(entries[0].params) == {"id": LED, "name": "LED", "action": "on"}
    assert entries[1].params["durationMs"] == 1000


def test_releasing_an_output_nobody_holds_notes_nothing(service: Service) -> None:
    service.controller.release(LED)

    assert _kinds(service) == []


def test_a_command_that_is_refused_notes_nothing(service: Service) -> None:
    with pytest.raises(PrimumError):
        service.controller.command(LED, "fade")

    assert _kinds(service) == []


def test_panic_is_noted_with_the_sequences_it_stops(service: Service) -> None:
    service.controller.start_sequence(ON)

    service.controller.panic()
    service.controller.panic()  # already on: not again
    service.controller.release_panic()

    entries = service.controller.trace.entries(after=2)
    assert [e.kind for e in entries] == ["panic.on", "sequence.stopped", "panic.released"]
    assert (entries[1].params["by"], entries[1].cause) == ("panic", entries[0].number)


def test_a_variable_set_through_the_api_is_noted_with_its_value(service: Service) -> None:
    service.controller.set_variable(BRIGHTNESS, 40)

    changed = _last(service, "variable.changed")
    assert dict(changed.params) == {
        "id": BRIGHTNESS,
        "name": "brightness",
        "value": 40,
        "by": "api",
    }


def test_the_steps_of_a_fade_and_the_levels_of_outputs_are_not_in_the_trace(
    service: Service,
) -> None:
    """Decisions, not measurements: a fade of two seconds is its start and nothing else."""
    service.controller.start_sequence(GLOW)
    for _ in range(50):
        service.after(0.02)

    assert _kinds(service) == ["sequence.started"]


def test_entries_carry_the_time_of_day_only_when_the_board_knows_it() -> None:
    known = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
    unsure, sure = Service(), Service(wall=lambda: known)

    unsure.controller.panic()
    sure.controller.panic()

    assert _last(unsure, "panic.on").time is None
    assert _last(sure, "panic.on").time == known


def test_an_output_that_fails_and_recovers_is_noted_once_each(
    service: Service, monkeypatch: pytest.MonkeyPatch
) -> None:
    line = service.hal.lines[17]
    failing = True
    write = type(line).write

    def stuck(self: object, active: bool) -> None:
        if failing:
            raise OSError("stuck")
        write(self, active)  # type: ignore[arg-type]  # the line it was called on

    monkeypatch.setattr(type(line), "write", stuck)
    service.controller.start_sequence(ON)
    service.after(5)
    service.after(5)
    failing = False
    service.after(5)

    kinds = _kinds(service)
    assert (kinds.count("output.failed"), kinds.count("output.recovered")) == (1, 1)


def _stuck(service: Service, monkeypatch: pytest.MonkeyPatch) -> None:
    """The LED no longer takes what it is written: every write of its line fails."""
    line = service.hal.lines[17]

    def stuck(self: object, active: bool) -> None:
        raise OSError("stuck")

    monkeypatch.setattr(type(line), "write", stuck)


def test_an_output_panic_cannot_make_safe_is_noted_once_however_often_panic_is_asked(
    service: Service, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.controller.command(LED, "on")
    _stuck(service, monkeypatch)

    for _ in range(3):
        with pytest.raises(PrimumError):
            service.controller.panic()

    kinds = _kinds(service)
    assert (kinds.count("panic.on"), kinds.count("output.failed")) == (1, 1)
    assert _last(service, "output.failed").cause == _last(service, "panic.on").number


def test_a_command_that_fails_on_the_hardware_is_still_noted(
    service: Service, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The output may have changed, and its test still expires: what follows in the trace
    needs the command that explains it."""
    _stuck(service, monkeypatch)

    with pytest.raises(OSError, match="stuck"):
        service.controller.command(LED, "on", duration_ms=1000)
    service.after(1)

    entries = service.controller.trace.entries(after=1)
    assert [e.kind for e in entries][:2] == ["output.commanded", "output.test_ended"]
    assert dict(entries[0].params) == {
        "id": LED,
        "name": "LED",
        "action": "on",
        "durationMs": 1000,
        "failed": True,
    }


def test_the_time_coming_to_be_known_is_noted_without_any_schedule() -> None:
    """The show has no schedules and no time zone: its entries carry the time all the same,
    and the trace says from when."""
    known: list[datetime] = []
    service = Service(wall=lambda: known[0] if known else None)
    service.controller.panic()
    known.append(datetime(2026, 11, 16, 9, 0, tzinfo=UTC))

    service.controller.release_panic()
    known.clear()
    service.controller.panic()

    assert _kinds(service) == [
        "panic.on",
        "time.known",
        "panic.released",
        "time.unknown",
        "panic.on",
    ]


def test_a_service_that_starts_knowing_the_time_says_so_after_its_first_entry() -> None:
    service = Service(wall=lambda: datetime(2026, 11, 16, 9, 0, tzinfo=UTC))

    assert _kinds(service, after=0) == ["service.started", "time.known"]


def test_a_kept_value_its_variable_no_longer_takes_is_noted() -> None:
    kept = {UUID(BRIGHTNESS): 500}
    loaded = package()
    brightness = next(v for v in loaded.variables if str(v.id) == BRIGHTNESS)
    persistent = tuple(
        replace(v, persistent=True) if v is brightness else v for v in loaded.variables
    )

    service = Service(replace(loaded, variables=persistent), kept=kept)

    dropped = _last(service, "variable.kept_value_dropped")
    assert dict(dropped.params) == {
        "id": BRIGHTNESS,
        "name": "brightness",
        "problem": "variable.value_out_of_range",
    }
    assert dropped.number == 2  # right after the service started


def test_each_trace_has_an_id_of_its_own() -> None:
    assert Trace().run != Trace().run


# --- events and automations ------------------------------------------------------------------

GO, CALL, SWAP = make_id(202), make_id(203), make_id(204)
VISITS, DIVISOR = make_id(61), make_id(63)
LAMP_ON, LAMP_ALT = make_id(30), make_id(40)


def _shop(swap: bool = False) -> Service:
    """An LED, two sequences of one exclusive group, a counter, and three automations on the
    event *Go*: *Count* (visits + 1, start *On*), *Never* (if visits > 100) and *Risky* (if
    10 / divisor > 1: start *Alt*)."""
    board = {"id": make_id(3), "name": "Pi", "model": "rpi4b"}
    led = {"id": make_id(4), "name": "LED", "type": "digital_output", "pin": 17}
    number = {"type": "integer", "min": 0, "max": 1000, "setting": True}
    variables = [
        {"id": VISITS, "name": "visits", "initial": 0, **number},
        {"id": DIVISOR, "name": "divisor", "initial": 1, **number},
    ]
    on: dict[str, object] = {"atMs": 0, "durationMs": 0, "action": "on"}
    count: dict[str, object] = {"action": "increment_variable", "variable": "visits"}
    files = {
        "project.json": make_file("project", 1, name="Traced"),
        "hardware.hw": make_file(
            "hardware", 2, boards=[board], elements=[{**led, "board": make_id(3)}]
        ),
        "shop.vars": make_file("variables", 60, constants=[], variables=variables),
        "on.sec": make_sequence(30, "On", 4, on, whenDone="hold", exclusiveGroup="lamp"),
        "alt.sec": make_sequence(40, "Alt", 4, on, whenDone="hold", exclusiveGroup="lamp"),
        "go.evt": make_file("event", 202, name="Go", source="ui"),
        "call.evt": make_file("event", 203, name="Call", source="api"),
        "count.auto": make_file(
            "automation",
            300,
            name="Count",
            when=[GO],
            do=[count, {"action": "start_sequence", "sequence": LAMP_ON}],
        ),
        "never.auto": make_file(
            "automation", 301, name="Never", when=[GO], do=[count], **{"if": "visits > 100"}
        ),
        "risky.auto": make_file(
            "automation",
            302,
            name="Risky",
            when=[CALL],
            do=[{"action": "start_sequence", "sequence": LAMP_ALT}],
            **{"if": "10 / divisor > 1"},
        ),
    }
    if swap:
        # *Swap*, on the event of its name: stop *On* and start *Alt*.
        files["swap.evt"] = make_file("event", 204, name="Swap", source="ui")
        files["swap.auto"] = make_file(
            "automation",
            303,
            name="Swap",
            when=[SWAP],
            do=[
                {"action": "stop_sequence", "sequence": LAMP_ON},
                {"action": "start_sequence", "sequence": LAMP_ALT},
            ],
        )
    return Service(package(compiled(files)))


def test_an_event_is_noted_with_what_each_automation_did_and_why() -> None:
    shop = _shop()

    shop.controller.fire_event(GO)

    entries = shop.controller.trace.entries(after=1)
    happened, acted, changed, started, did_not = entries
    assert (happened.kind, dict(happened.params)) == (
        "event.happened",
        {"id": GO, "name": "Go", "source": "ui"},
    )
    assert (acted.kind, acted.params["name"], acted.cause) == (
        "automation.acted",
        "Count",
        happened.number,
    )
    assert (changed.kind, changed.params["value"], changed.params["by"], changed.cause) == (
        "variable.changed",
        1,
        "automation",
        acted.number,
    )
    assert (started.kind, started.params["name"], started.params["by"], started.cause) == (
        "sequence.started",
        "On",
        "automation",
        acted.number,
    )
    assert (did_not.kind, did_not.params["name"], did_not.cause) == (
        "automation.did_not_act",
        "Never",
        happened.number,
    )


def test_a_sequence_stopped_by_its_exclusive_group_says_so() -> None:
    shop = _shop()
    shop.controller.fire_event(GO)  # On runs
    shop.controller.set_variable(DIVISOR, 5)

    shop.controller.fire_event(CALL)  # Risky starts Alt, of the same group

    stopped = _last(shop, "sequence.stopped")
    assert (stopped.params["name"], stopped.params["by"]) == ("On", "exclusive_group")
    assert _last(shop, "sequence.started").params["name"] == "Alt"


def test_a_sequence_an_automation_stops_is_stopped_by_it_whatever_else_it_starts() -> None:
    """Stop On, start Alt, of the same exclusive group: On was stopped by the automation,
    which asked for it, not by the group."""
    shop = _shop(swap=True)
    shop.controller.fire_event(GO)  # On runs

    shop.controller.fire_event(SWAP)

    stopped = _last(shop, "sequence.stopped")
    assert (stopped.params["name"], stopped.params["by"]) == ("On", "automation")


def test_a_condition_that_fails_is_noted_with_its_reason() -> None:
    shop = _shop()
    shop.controller.set_variable(DIVISOR, 0)

    shop.controller.fire_event(CALL)

    failed = _last(shop, "automation.failed")
    assert dict(failed.params) == {
        "id": make_id(302),
        "name": "Risky",
        "problem": "automation.condition_failed",
        "reason": "division_by_zero",
    }
    assert failed.cause == _last(shop, "event.happened").number


def test_an_action_that_fails_is_noted_after_what_the_others_did(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shop = _shop()

    def broken(*_: object) -> None:
        raise PrimumError(ErrorCode.SEQUENCE_UNKNOWN, {"id": LAMP_ON})

    monkeypatch.setattr(Engine, "start", broken)

    shop.controller.fire_event(GO)

    assert _kinds(shop)[:4] == [
        "event.happened",
        "automation.acted",
        "variable.changed",
        "automation.failed",
    ]
    failed = _last(shop, "automation.failed")
    assert dict(failed.params) == {
        "id": make_id(300),
        "name": "Count",
        "problem": "automation.action_failed",
        "action": "start_sequence",
        "failure": "sequence.unknown",
    }


def test_an_event_fired_during_panic_is_refused_and_not_noted() -> None:
    shop = _shop()
    shop.controller.panic()

    with pytest.raises(PrimumError):
        shop.controller.fire_event(GO)

    assert _kinds(shop) == ["panic.on"]


# --- the API ---------------------------------------------------------------------------------


def test_the_api_gives_the_trace_and_what_followed_an_entry(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        client.post(f"/api/sequences/{ON}/start")
        client.post(f"/api/sequences/{ON}/stop")
        whole = client.get("/api/trace").json()
        rest = client.get("/api/trace", params={"after": 2}).json()

    assert [entry["kind"] for entry in whole["entries"]] == [
        "service.started",
        "sequence.started",
        "sequence.stopped",
    ]
    assert (whole["first"], whole["last"]) == (1, 3)
    assert [entry["number"] for entry in rest["entries"]] == [3]
    started = whole["entries"][1]
    assert started["params"] == {"id": ON, "name": "On", "by": "api"}
    assert (started["cause"], started["time"], isinstance(started["atMs"], int)) == (
        None,
        None,
        True,
    )


def test_the_api_refuses_a_number_that_is_not_one(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        answer = client.get("/api/trace", params={"after": -1})

    assert (answer.status_code, answer.json()["code"]) == (422, "request.invalid")


def test_the_websocket_sends_what_is_kept_and_then_each_entry_as_it_is_noted(
    tmp_path: Path,
) -> None:
    waiting = ThreadPoolExecutor(max_workers=1)
    try:
        with running(tmp_path) as (client, _), client.websocket_connect("/api/trace/ws") as ws:
            kept = waiting.submit(ws.receive_json).result(timeout=WAIT_S)
            client.post("/api/panic")
            live = waiting.submit(ws.receive_json).result(timeout=WAIT_S)
    finally:
        waiting.shutdown(wait=False)

    assert [entry["kind"] for entry in kept["entries"]] == ["service.started"]
    assert [entry["kind"] for entry in live["entries"]] == ["panic.on"]
    assert live["entries"][0]["number"] == 2


def test_the_websocket_always_answers_at_once_also_with_nothing_to_send(tmp_path: Path) -> None:
    """A client that comes back after the service restarted asks for what follows an entry
    the new trace has not reached. It must be told where the trace is, not left waiting."""
    waiting = ThreadPoolExecutor(max_workers=1)
    try:
        with (
            running(tmp_path) as (client, _),
            client.websocket_connect("/api/trace/ws?after=500") as ws,
        ):
            first = waiting.submit(ws.receive_json).result(timeout=WAIT_S)
            run = client.get("/api/trace").json()["run"]
    finally:
        waiting.shutdown(wait=False)

    assert (first["entries"], first["last"], first["run"]) == ([], 1, run)


def test_two_services_never_share_the_id_of_their_trace(tmp_path: Path) -> None:
    with running(tmp_path) as (client, _):
        before = client.get("/api/trace").json()["run"]
    with running(tmp_path) as (client, _):
        after = client.get("/api/trace").json()["run"]

    assert before != after


def test_the_websocket_refuses_a_number_that_is_not_one(tmp_path: Path) -> None:
    with (
        running(tmp_path) as (client, _),
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/api/trace/ws?after=-1"),
    ):
        pass


def test_the_websocket_starts_after_the_entry_it_is_told(tmp_path: Path) -> None:
    waiting = ThreadPoolExecutor(max_workers=1)
    try:
        with running(tmp_path) as (client, _):
            client.post("/api/panic")
            client.delete("/api/panic")
            with client.websocket_connect("/api/trace/ws?after=2") as ws:
                kept = waiting.submit(ws.receive_json).result(timeout=WAIT_S)
    finally:
        waiting.shutdown(wait=False)

    assert [entry["kind"] for entry in kept["entries"]] == ["panic.released"]
