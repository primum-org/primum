"""Persistent variables: their values are kept on the board and found again (decision 0031)."""

import json
import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from uuid import UUID

import pytest

from primum_core.values import Value
from primum_runtime import stored
from primum_runtime.api.saving import RETRY_S, SAVE_DELAY_S, VariableSaver
from primum_runtime.errors import ErrorCode, PrimumError
from show_service import Service, compiled, make_file, make_id, package, running

VISITS, LEVEL, NOTE, SCRATCH = (make_id(number) for number in (61, 62, 63, 64))
GO = make_id(202)
PROJECT, OTHER_PROJECT = UUID(make_id(1)), UUID(make_id(999))


def _document(**visits: object) -> dict[str, object]:
    """A Pi with an LED and four variables: *visits* (an integer, 0 to 10), *level* (a
    number) and *note* (a text) are persistent; *scratch* is not. The event *Go* counts a
    visit."""
    board = {"id": make_id(3), "name": "Pi", "model": "rpi4b"}
    led = {"id": make_id(4), "name": "LED", "type": "digital_output", "pin": 17}
    kept = {"setting": True, "persistent": True}
    counter = {"type": "integer", "initial": 0, "min": 0, "max": 10, **visits}
    variables = [
        {"id": VISITS, "name": "visits", **counter, **kept},
        {"id": LEVEL, "name": "level", "type": "number", "initial": 0.5, **kept},
        {"id": NOTE, "name": "note", "type": "text", "initial": "", **kept},
        {"id": SCRATCH, "name": "scratch", "type": "integer", "initial": 0, "setting": True},
    ]
    count: dict[str, object] = {"action": "increment_variable", "variable": "visits"}
    files = {
        "project.json": make_file("project", 1, name="Counter"),
        "hardware.hw": make_file(
            "hardware", 2, boards=[board], elements=[{**led, "board": make_id(3)}]
        ),
        "shop.vars": make_file("variables", 60, constants=[], variables=variables),
        "go.evt": make_file("event", 202, name="Go", source="ui"),
        "count.auto": make_file("automation", 300, name="Count", when=[GO], do=[count]),
    }
    return compiled(files)


DOCUMENT = _document()


def _values(service: Service) -> dict[str, Value]:
    return {v.id: v.value for v in service.controller.state().variables}


def _kept(tmp_path: Path, content: bytes) -> None:
    """Put ``content`` where the values of the project are kept."""
    file = stored.path(tmp_path, PROJECT)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(content)


def _aside_file(tmp_path: Path) -> Path:
    file = stored.path(tmp_path, PROJECT)
    return file.with_name(file.name + stored.ASIDE_SUFFIX)


# --- the file --------------------------------------------------------------------------------


def test_values_kept_are_found_again_with_their_types(tmp_path: Path) -> None:
    values: dict[UUID, Value] = {
        UUID(VISITS): 3,
        UUID(LEVEL): 0.25,
        UUID(NOTE): "día",
        UUID(SCRATCH): True,
    }

    stored.write(tmp_path, PROJECT, values)
    found = stored.read(tmp_path, PROJECT)

    assert found == values
    assert [type(found[key]) for key in values] == [int, float, str, bool]


def test_nothing_kept_gives_no_values(tmp_path: Path) -> None:
    assert stored.read(tmp_path, PROJECT) == {}


def test_values_of_another_project_are_not_this_ones(tmp_path: Path) -> None:
    stored.write(tmp_path, OTHER_PROJECT, {UUID(VISITS): 3})

    assert stored.read(tmp_path, PROJECT) == {}


def _kept_file(**fields: object) -> str:
    return json.dumps({"version": 1, "project": str(PROJECT), "values": {}, **fields})


@pytest.mark.parametrize(
    "content",
    [
        "",
        "{",
        "[]",
        _kept_file(version=2),
        _kept_file(project="not an id"),
        _kept_file(values={"not an id": 1}),
        _kept_file(values={VISITS: [1]}),
        json.dumps({"version": 1, "project": str(PROJECT)}),
    ],
)
def test_a_file_that_does_not_say_what_it_should_gives_no_values_and_does_not_fail(
    tmp_path: Path, content: str, caplog: pytest.LogCaptureFixture
) -> None:
    _kept(tmp_path, content.encode())

    assert stored.read(tmp_path, PROJECT) == {}
    assert "kept variables" in caplog.text


@pytest.mark.parametrize(
    "content",
    [
        b"\xff\xfe\x00\x9c\x80garbage",  # not text at all
        b'{"version": 1, "project": "\xc3\x28"}',  # text cut in the middle of a letter
        b"[" * 100_000,  # nested deeper than anything reads
    ],
)
def test_a_file_that_is_not_even_text_gives_no_values_and_does_not_fail(
    tmp_path: Path, content: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    _kept(tmp_path, content)

    assert stored.read(tmp_path, PROJECT) == {}
    assert "kept variables" in caplog.text


def test_a_write_replaces_the_file_whole_and_leaves_nothing_else(tmp_path: Path) -> None:
    stored.write(tmp_path, PROJECT, {UUID(VISITS): 3})

    stored.write(tmp_path, PROJECT, {UUID(VISITS): 4})

    file = stored.path(tmp_path, PROJECT)
    assert list(file.parent.iterdir()) == [file]
    assert json.loads(file.read_text())["values"] == {VISITS: 4}


def test_what_is_about_to_be_replaced_can_be_set_aside(tmp_path: Path) -> None:
    stored.write(tmp_path, PROJECT, {UUID(VISITS): 7})

    stored.set_aside(tmp_path, PROJECT)
    stored.write(tmp_path, PROJECT, {UUID(VISITS): 0})

    aside = json.loads(_aside_file(tmp_path).read_text())
    assert (aside["project"], aside["values"]) == (str(PROJECT), {VISITS: 7})


def test_setting_aside_nothing_does_nothing(tmp_path: Path) -> None:
    stored.set_aside(tmp_path, PROJECT)

    assert list(tmp_path.iterdir()) == []


def test_each_project_has_values_of_its_own_and_neither_touches_the_others(
    tmp_path: Path,
) -> None:
    stored.write(tmp_path, PROJECT, {UUID(VISITS): 3})

    stored.write(tmp_path, OTHER_PROJECT, {UUID(VISITS): 8})

    assert stored.read(tmp_path, PROJECT) == {UUID(VISITS): 3}
    assert stored.read(tmp_path, OTHER_PROJECT) == {UUID(VISITS): 8}


def _legacy(tmp_path: Path, project: UUID, visits: int) -> None:
    """The one file of before block 4.5b, for one project."""
    document = {"version": 1, "project": str(project), "values": {VISITS: visits}}
    (tmp_path / stored.LEGACY_NAME).write_text(json.dumps(document), encoding="utf-8")


def test_the_one_file_of_before_is_still_read_for_the_project_it_names(tmp_path: Path) -> None:
    _legacy(tmp_path, PROJECT, 5)

    assert stored.read(tmp_path, PROJECT) == {UUID(VISITS): 5}
    assert stored.read(tmp_path, OTHER_PROJECT) == {}


def test_a_project_with_a_file_of_its_own_no_longer_reads_the_one_of_before(
    tmp_path: Path,
) -> None:
    _legacy(tmp_path, PROJECT, 5)

    stored.write(tmp_path, PROJECT, {UUID(VISITS): 6})

    assert stored.read(tmp_path, PROJECT) == {UUID(VISITS): 6}


def test_a_write_that_fails_says_so_and_keeps_what_was_there(tmp_path: Path) -> None:
    not_a_folder = tmp_path / "file"
    not_a_folder.write_text("in the way", encoding="utf-8")

    with pytest.raises(PrimumError) as refused:
        stored.write(not_a_folder, PROJECT, {UUID(VISITS): 3})

    assert refused.value.code is ErrorCode.VARIABLES_UNWRITABLE
    assert refused.value.params["path"] == str(stored.path(not_a_folder, PROJECT))


# --- the controller --------------------------------------------------------------------------


def _service(kept: dict[str, Value], document: dict[str, object] = DOCUMENT) -> Service:
    """A controller that starts with ``kept`` as the values found on the board."""
    on_disk = {UUID(variable): value for variable, value in kept.items()}
    return Service(package(document), kept=on_disk)


def test_a_persistent_variable_starts_at_the_value_it_was_kept_at() -> None:
    service = _service({VISITS: 7, LEVEL: 0.25, NOTE: "hola"})

    assert _values(service) == {VISITS: 7, LEVEL: 0.25, NOTE: "hola", SCRATCH: 0}


def test_a_variable_that_is_not_persistent_starts_at_its_initial_value() -> None:
    service = _service({SCRATCH: 9})

    assert _values(service)[SCRATCH] == 0


def test_a_persistent_variable_never_kept_starts_at_its_initial_value() -> None:
    service = _service({VISITS: 7})

    assert (_values(service)[LEVEL], _values(service)[NOTE]) == (0.5, "")


@pytest.mark.parametrize("kept", [11, -1, 2.5, "three", True])
def test_a_value_its_variable_no_longer_takes_gives_way_to_the_initial_one(
    kept: Value, caplog: pytest.LogCaptureFixture
) -> None:
    """A new package may have changed the type of the variable or its limits."""
    service = _service({VISITS: kept, LEVEL: 0.25})

    assert _values(service)[VISITS] == 0
    assert _values(service)[LEVEL] == 0.25  # the others keep theirs
    assert "visits was kept at" in caplog.text


def test_only_persistent_variables_are_worth_keeping() -> None:
    service = _service({})
    service.controller.set_variable(SCRATCH, 5)
    service.controller.set_variable(VISITS, 5)

    assert service.controller.persistent_values() == {
        UUID(VISITS): 5,
        UUID(LEVEL): 0.5,
        UUID(NOTE): "",
    }


def test_the_state_says_while_the_values_are_not_kept() -> None:
    service = _service({})
    service.states.clear()

    service.controller.values_kept(False)
    service.controller.values_kept(False)
    service.controller.values_kept(True)

    assert [state.variables_unsaved for state in service.states] == [True, False]


# --- saving as they change -------------------------------------------------------------------


class _Loop:
    """What the saver asks of the event loop, in the test's hand: timers that fire when
    told, and writes that run when told, and fail if told to."""

    def __init__(self) -> None:
        self.timers: list[tuple[float, Callable[[], None]]] = []
        self.written: list[dict[UUID, Value]] = []
        self.failing = False
        self.held: list[Callable[[], None]] = []
        self.hold = False

    def call_later(self, delay_s: float, callback: Callable[[], None]) -> "_Loop":
        self.timers.append((delay_s, callback))
        return self

    def cancel(self) -> None:
        self.timers.clear()

    def fire(self) -> None:
        [(_, callback)] = self.timers
        self.timers.clear()
        callback()

    def write(self, values: Mapping[UUID, Value]) -> None:
        if self.failing:
            raise PrimumError(ErrorCode.VARIABLES_UNWRITABLE, {"path": "p", "detail": "full"})
        self.written.append(dict(values))

    def submit(
        self, work: Callable[[], None], done: Callable[[BaseException | None], None]
    ) -> None:
        def run() -> None:
            try:
                work()
            except Exception as error:
                done(error)
            else:
                done(None)

        if self.hold:
            self.held.append(run)
        else:
            run()


def _saving(service: Service, kept: dict[UUID, Value] | None = None) -> tuple[_Loop, VariableSaver]:
    loop = _Loop()
    on_disk = service.controller.persistent_values() if kept is None else kept
    saver = VariableSaver(service.controller, loop.write, loop.call_later, loop.submit, on_disk)
    return loop, saver


def test_a_change_is_written_a_moment_later_not_at_once() -> None:
    service = _service({})
    loop, _ = _saving(service)

    service.controller.set_variable(VISITS, 4)
    armed = [delay for delay, _ in loop.timers]
    before = list(loop.written)
    loop.fire()

    assert (armed, before) == ([SAVE_DELAY_S], [])
    assert [values[UUID(VISITS)] for values in loop.written] == [4]


def test_many_changes_in_a_row_are_one_write_of_the_last_values() -> None:
    service = _service({})
    loop, _ = _saving(service)

    for _ in range(6):
        service.controller.fire_event(GO)
    timers = len(loop.timers)
    loop.fire()

    assert timers == 1
    assert [values[UUID(VISITS)] for values in loop.written] == [6]
    assert loop.timers == []  # nothing pending: nothing armed


def test_a_change_of_a_variable_that_is_not_persistent_writes_nothing() -> None:
    service = _service({})
    loop, _ = _saving(service)

    service.controller.set_variable(SCRATCH, 4)

    assert (loop.timers, loop.written) == ([], [])


def test_a_value_set_back_before_the_write_is_not_written() -> None:
    service = _service({})
    loop, _ = _saving(service)
    service.controller.set_variable(VISITS, 4)

    service.controller.set_variable(VISITS, 0)
    loop.fire()

    assert loop.written == []


def test_what_changes_while_a_write_is_under_way_is_written_after_it() -> None:
    service = _service({})
    loop, _ = _saving(service)
    service.controller.set_variable(VISITS, 4)
    loop.hold = True
    loop.fire()

    service.controller.set_variable(VISITS, 5)  # the card is still busy with the 4
    during = len(loop.timers)
    loop.held.pop()()
    loop.hold = False
    loop.fire()

    assert during == 0  # not a second write on top of the first
    assert [values[UUID(VISITS)] for values in loop.written] == [4, 5]


def test_values_that_start_differently_than_they_were_kept_are_written() -> None:
    """A kept value that no longer fits gave way to the initial one: that is the value now."""
    service = _service({VISITS: 99})
    loop, _ = _saving(service, {UUID(VISITS): 99})

    loop.fire()

    assert loop.written[0][UUID(VISITS)] == 0


def test_a_write_that_fails_is_told_once_and_tried_again_until_it_works(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = _service({})
    loop, _ = _saving(service)
    loop.failing = True
    service.controller.set_variable(VISITS, 4)

    loop.fire()
    failed = (service.controller.state().variables_unsaved, [d for d, _ in loop.timers])
    loop.fire()
    loop.failing = False
    loop.fire()

    assert failed == (True, [RETRY_S])
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert service.controller.state().variables_unsaved is False
    assert [values[UUID(VISITS)] for values in loop.written] == [4]


def test_a_failed_write_is_over_when_nothing_is_left_to_write() -> None:
    """The write failed, and then the value went back to what is on the board: there is
    nothing to keep any more, and the state must stop saying there is."""
    service = _service({})
    loop, _ = _saving(service)
    loop.failing = True
    service.controller.set_variable(VISITS, 4)
    loop.fire()
    failed = service.controller.state().variables_unsaved

    service.controller.set_variable(VISITS, 0)
    loop.fire()  # the retry: nothing pending

    assert (failed, service.controller.state().variables_unsaved) == (True, False)
    assert (loop.written, loop.timers) == ([], [])


def test_a_write_under_way_never_lands_over_the_one_made_on_closing() -> None:
    """The thread of an earlier write may get to the card after the last one: what it
    carries is older, and must not replace it."""
    service = _service({})
    loop, saver = _saving(service)
    service.controller.set_variable(VISITS, 4)
    loop.hold = True
    loop.fire()  # the write of 4 is handed over, and has not run
    service.controller.set_variable(VISITS, 5)

    saver.close()  # writes 5, here and now
    loop.held.pop()()  # and only then the thread runs

    assert [values[UUID(VISITS)] for values in loop.written] == [5]
    assert loop.timers == []  # and nothing is armed after closing


def test_closing_while_a_write_is_under_way_has_the_last_word() -> None:
    """A write of 4 is in its thread; the variable goes back to the 0 that is on the board
    and the service stops. Nothing looks pending, but the thread would leave a 4 that the
    variable no longer has."""
    service = _service({})
    loop, saver = _saving(service)
    service.controller.set_variable(VISITS, 4)
    loop.hold = True
    loop.fire()  # the write of 4 is handed over, and has not run
    service.controller.set_variable(VISITS, 0)

    saver.close()
    loop.held.pop()()  # the thread gets there after

    assert [values[UUID(VISITS)] for values in loop.written] == [0]


def test_closing_writes_what_is_pending_at_once() -> None:
    service = _service({})
    loop, saver = _saving(service)
    service.controller.set_variable(VISITS, 4)

    saver.close()

    assert [values[UUID(VISITS)] for values in loop.written] == [4]
    assert loop.timers == []


def test_closing_with_nothing_pending_writes_nothing() -> None:
    service = _service({})
    loop, saver = _saving(service)

    saver.close()

    assert loop.written == []


def test_panic_leaves_the_values_as_they_are() -> None:
    service = _service({VISITS: 7})

    service.controller.panic()

    assert service.controller.persistent_values()[UUID(VISITS)] == 7


# --- the service -----------------------------------------------------------------------------


def _run(
    tmp_path: Path, document: dict[str, object], *requests: tuple[str, object]
) -> dict[str, Value]:
    """Start the service on ``tmp_path`` as its data directory, set the variables asked,
    stop it, and say what the status gave before it stopped."""
    with running(tmp_path, document, data_dir=tmp_path) as (client, _):
        for variable, value in requests:
            answer = client.put(f"/api/variables/{variable}", json={"value": value})
            assert answer.status_code == 200, answer.text
        state = client.get("/api/status").json()
    return {variable["id"]: variable["value"] for variable in state["variables"]}


def test_a_service_that_restarts_finds_its_persistent_variables_where_they_were(
    tmp_path: Path,
) -> None:
    _run(tmp_path, DOCUMENT, (VISITS, 7), (NOTE, "hola"), (SCRATCH, 4))

    found = _run(tmp_path, DOCUMENT)

    assert found == {VISITS: 7, LEVEL: 0.5, NOTE: "hola", SCRATCH: 0}


def test_a_new_package_of_the_same_project_finds_them_too(tmp_path: Path) -> None:
    _run(tmp_path, DOCUMENT, (VISITS, 7))

    found = _run(tmp_path, _document(max=20))

    assert found[VISITS] == 7


def test_a_new_package_whose_variable_no_longer_takes_the_value_starts_it_again(
    tmp_path: Path,
) -> None:
    _run(tmp_path, DOCUMENT, (VISITS, 7))

    found = _run(tmp_path, _document(max=5))
    again = _run(tmp_path, _document(max=5))

    assert (found[VISITS], again[VISITS]) == (0, 0)


@pytest.mark.parametrize("content", [b"{", b"\xff\xfe\x00\x9c\x80garbage"])
def test_a_service_whose_values_cannot_be_read_starts_at_the_initial_ones(
    tmp_path: Path, content: bytes
) -> None:
    _kept(tmp_path, content)

    found = _run(tmp_path, DOCUMENT)

    assert found[VISITS] == 0
    assert _aside_file(tmp_path).read_bytes() == content  # set aside


def _aside(tmp_path: Path) -> dict[str, object] | None:
    path = _aside_file(tmp_path)
    return json.loads(path.read_text(encoding="utf-8"))["values"] if path.exists() else None


def test_kept_values_that_a_new_package_drops_are_set_aside_before_they_are_replaced(
    tmp_path: Path,
) -> None:
    """Going back to the package before must be able to find the counter again."""
    _run(tmp_path, DOCUMENT, (VISITS, 7))

    _run(tmp_path, _document(max=5))

    assert _aside(tmp_path) == {VISITS: 7, LEVEL: 0.5, NOTE: ""}


def test_values_of_another_project_are_left_as_they_are(tmp_path: Path) -> None:
    stored.write(tmp_path, OTHER_PROJECT, {UUID(VISITS): 9})

    _run(tmp_path, DOCUMENT, (VISITS, 1))

    assert stored.read(tmp_path, OTHER_PROJECT) == {UUID(VISITS): 9}
    assert _aside(tmp_path) is None  # nothing was dropped: nothing to set aside


def test_nothing_is_set_aside_when_every_kept_value_is_taken(tmp_path: Path) -> None:
    _run(tmp_path, DOCUMENT, (VISITS, 7))

    _run(tmp_path, DOCUMENT, (VISITS, 8))
    _run(tmp_path, _document(max=20))

    assert _aside(tmp_path) is None


def test_the_status_says_which_variables_are_persistent(tmp_path: Path) -> None:
    with running(tmp_path, DOCUMENT, data_dir=tmp_path) as (client, _):
        state = client.get("/api/status").json()

    assert {v["name"]: v["persistent"] for v in state["variables"]} == {
        "visits": True,
        "level": True,
        "note": True,
        "scratch": False,
    }
    assert state["variablesUnsaved"] is False
