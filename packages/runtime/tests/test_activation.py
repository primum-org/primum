"""Packages on a board: stored, activated, put back (decision 0033)."""

import json
import threading
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from primum_runtime import deployed
from primum_runtime.api import create_app
from primum_runtime.board import load_board
from primum_runtime.config import parse_config
from primum_runtime.deployed import DIRECTORY, MAX_BYTES, STATE_NAME, Deployed, Pointers
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.hal import Hal, SimulatedHal
from primum_runtime.package import LoadedPackage
from show_service import MANIFESTS, WAIT_S, compiled, make_file, make_id, make_sequence

LED, ON, VISITS = make_id(4), make_id(30), make_id(61)


def _document(
    name: str = "Shop", pin: int = 17, maximum: int = 10, project: int = 1
) -> dict[str, object]:
    """A Pi with an LED on ``pin``, the sequence *On* that holds it on, and a persistent
    counter of visits, up to ``maximum``. The same project, whatever its name, unless
    ``project`` says another."""
    board = {"id": make_id(3), "name": "Pi", "model": "rpi4b"}
    led = {"id": LED, "name": "LED", "type": "digital_output", "pin": pin, "board": make_id(3)}
    visits = {"id": VISITS, "name": "visits", "type": "integer", "initial": 0, "min": 0}
    kept = {"max": maximum, "setting": True, "persistent": True}
    on: dict[str, object] = {"atMs": 0, "durationMs": 0, "action": "on"}
    return compiled(
        {
            "project.json": make_file("project", project, name=name),
            "hardware.hw": make_file("hardware", 2, boards=[board], elements=[led]),
            "shop.vars": make_file("variables", 60, constants=[], variables=[{**visits, **kept}]),
            "on.sec": make_sequence(30, "On", 4, on, whenDone="hold"),
        }
    )


FIRST, SECOND = _document("First", 17), _document("Second", 27)
FIRST_HASH, SECOND_HASH = str(FIRST["hash"]), str(SECOND["hash"])


def _bytes(document: dict[str, object]) -> bytes:
    return json.dumps(document).encode()


# --- the packages a board keeps --------------------------------------------------------------


@pytest.fixture
def kept(tmp_path: Path) -> Deployed:
    return Deployed(tmp_path, MANIFESTS, "rpi4b")


def test_a_board_starts_with_no_packages(kept: Deployed) -> None:
    assert kept.pointers() == Pointers()


def test_a_package_stored_is_staged_and_nothing_else_changes(kept: Deployed) -> None:
    loaded = kept.store(_bytes(FIRST))

    assert loaded.package.hash == FIRST_HASH
    assert kept.pointers() == Pointers(staged=FIRST_HASH)


def test_activating_makes_it_the_active_one_and_the_one_before_the_previous(
    kept: Deployed,
) -> None:
    kept.store(_bytes(FIRST))
    kept.activate(FIRST_HASH)
    kept.store(_bytes(SECOND))

    after = kept.activate(SECOND_HASH)

    assert after == Pointers(active=SECOND_HASH, previous=FIRST_HASH)
    assert kept.pointers() == after


def test_activating_the_previous_one_swaps_them_so_it_can_be_undone(kept: Deployed) -> None:
    for document in (FIRST, SECOND):
        kept.store(_bytes(document))
        kept.activate(str(document["hash"]))

    back = kept.activate(FIRST_HASH)
    again = kept.activate(SECOND_HASH)

    assert back == Pointers(active=FIRST_HASH, previous=SECOND_HASH)
    assert again == Pointers(active=SECOND_HASH, previous=FIRST_HASH)


def test_only_the_packages_that_are_pointed_at_are_kept(kept: Deployed, tmp_path: Path) -> None:
    third = _document("Third", 22)
    for document in (FIRST, SECOND, third):
        kept.store(_bytes(document))
        kept.activate(str(document["hash"]))
    kept.store(_bytes(_document("Fourth", 23)))
    kept.store(_bytes(_document("Fifth", 24)))  # replaces the one staged before

    files = sorted(path.name for path in (tmp_path / DIRECTORY).glob("*.package.json"))

    assert len(files) == 3  # active, previous, staged
    assert FIRST_HASH.removeprefix("sha256:") + ".package.json" not in files


def test_a_package_kept_is_read_and_checked_again(kept: Deployed, tmp_path: Path) -> None:
    kept.store(_bytes(FIRST))
    file = next((tmp_path / DIRECTORY).glob("*.package.json"))
    file.write_bytes(_bytes({**FIRST, "kind": "nothing"}))

    with pytest.raises(PrimumError) as refused:
        kept.load(FIRST_HASH)

    assert refused.value.code is ErrorCode.PACKAGE_INVALID


@pytest.mark.parametrize(
    "package",
    [SECOND_HASH, "sha256:" + "0" * 64, "../../etc/passwd", "sha256:../" + "0" * 61, ""],
)
def test_a_package_that_is_not_kept_cannot_be_loaded_or_activated(
    kept: Deployed, package: str
) -> None:
    kept.store(_bytes(FIRST))

    for ask in (kept.load, kept.activate):
        with pytest.raises(PrimumError) as refused:
            ask(package)
        assert refused.value.code is ErrorCode.PACKAGE_NOT_STORED


def test_a_package_the_board_cannot_run_is_not_kept(kept: Deployed, tmp_path: Path) -> None:
    with pytest.raises(PrimumError) as refused:
        kept.store(_bytes({**FIRST, "kind": "nothing"}))

    assert refused.value.code is ErrorCode.PACKAGE_INVALID
    assert kept.pointers() == Pointers()
    assert list((tmp_path / DIRECTORY).glob("*")) == [] or not (tmp_path / DIRECTORY).exists()


def test_a_package_for_another_board_than_the_services_is_not_kept(tmp_path: Path) -> None:
    other = Deployed(tmp_path, MANIFESTS, "rpi5")

    with pytest.raises(PrimumError) as refused:
        other.store(_bytes(FIRST))

    assert (refused.value.code, dict(refused.value.params)) == (
        ErrorCode.PACKAGE_BOARD_UNSUPPORTED,
        {"board": "rpi4b", "available": ("rpi5",)},
    )
    assert other.pointers() == Pointers()


def test_a_package_too_large_is_refused_before_it_is_read(kept: Deployed) -> None:
    with pytest.raises(PrimumError) as refused:
        kept.store(b" " * (MAX_BYTES + 1))

    assert refused.value.code is ErrorCode.PACKAGE_TOO_LARGE


@pytest.mark.parametrize(
    "content",
    [b"", b"{", b"\xff\xfe", b"[]", b'{"version": 2}', b'{"version": 1, "active": "x"}'],
)
def test_a_state_that_cannot_be_used_is_no_package_at_all(
    kept: Deployed, tmp_path: Path, content: bytes
) -> None:
    kept.store(_bytes(FIRST))
    (tmp_path / DIRECTORY / STATE_NAME).write_bytes(content)

    assert kept.pointers() == Pointers()


# --- the service -----------------------------------------------------------------------------


class _Board:
    """The HALs a service opened, one each time what it runs changed; the last is the one
    in use. ``fail`` makes the next one refuse to open."""

    def __init__(self, fail: bool = False) -> None:
        self.hals: list[SimulatedHal] = []
        self.fail = fail

    def open(self) -> Hal:
        if self.fail:
            self.fail = False
            raise PrimumError(ErrorCode.HAL_CHIP_NOT_FOUND, {"chip": "gone"})
        self.hals.append(SimulatedHal(load_board("rpi4b")))
        return self.hals[-1]

    @property
    def hal(self) -> SimulatedHal:
        return self.hals[-1]


@contextmanager
def _service(
    data_dir: Path, *options: str, fail: bool = False
) -> Generator[tuple[TestClient, _Board]]:
    """A service that runs what is activated on it, keeping what it keeps in ``data_dir``.
    With ``fail``, the first HAL it asks for does not open."""
    config = parse_config(["--simulate", "--no-pairing", "--data-dir", str(data_dir), *options], {})
    board = _Board(fail)
    with TestClient(create_app(config, open_hal=board.open)) as client:
        yield client, board


def _give(client: TestClient, document: dict[str, object], activate: bool = True) -> None:
    stored = client.put("/api/package", content=_bytes(document))
    assert stored.status_code == 200, stored.text
    if activate:
        activated = client.post("/api/package/activate", json={"hash": document["hash"]})
        assert activated.status_code == 200, activated.text


def _outputs(client: TestClient) -> list[tuple[str, bool]]:
    return [(o["name"], o["on"]) for o in client.get("/api/status").json()["outputs"]]


def _kinds(client: TestClient) -> list[str]:
    return [entry["kind"] for entry in client.get("/api/trace").json()["entries"]]


def test_a_service_with_no_package_starts_with_nothing_and_says_so(tmp_path: Path) -> None:
    with _service(tmp_path) as (client, _):
        packages = client.get("/api/package").json()
        state = client.get("/api/status").json()

    assert packages == {
        "running": None,
        "active": None,
        "previous": None,
        "staged": None,
        "problem": None,
        "fixed": False,
    }
    assert (state["outputs"], state["inputs"], state["sequences"]) == ([], [], [])


def test_storing_a_package_changes_nothing_that_runs(tmp_path: Path) -> None:
    with _service(tmp_path) as (client, board):
        _give(client, FIRST, activate=False)
        packages = client.get("/api/package").json()
        outputs, opened = _outputs(client), len(board.hals)

    assert (packages["staged"], packages["active"], packages["running"]) == (
        {"hash": FIRST_HASH, "project": "First"},
        None,
        None,
    )
    assert (outputs, opened) == ([], 1)


def test_activating_a_package_runs_it(tmp_path: Path) -> None:
    with _service(tmp_path) as (client, board):
        _give(client, FIRST)
        client.post(f"/api/sequences/{ON}/start")
        packages = client.get("/api/package").json()
        outputs, lit = _outputs(client), board.hal.lines[17].active

    running = {"hash": FIRST_HASH, "project": "First"}
    assert (packages["running"], packages["active"], packages["staged"]) == (running, running, None)
    assert (outputs, lit) == ([("LED", True)], True)


def test_activating_another_stops_everything_and_starts_it_from_nothing(tmp_path: Path) -> None:
    with _service(tmp_path) as (client, board):
        _give(client, FIRST)
        client.post(f"/api/sequences/{ON}/start")
        first_hal = board.hal

        _give(client, SECOND)
        state = client.get("/api/status").json()
        packages = client.get("/api/package").json()

    assert not first_hal.lines[17].active  # made safe, and let go of
    assert 27 in board.hal.lines  # the new package's LED is on another pin
    assert [(o["name"], o["on"]) for o in state["outputs"]] == [("LED", False)]
    assert [s["running"] for s in state["sequences"]] == [False]
    assert (packages["active"]["project"], packages["previous"]["project"]) == ("Second", "First")


def test_the_previous_package_can_be_put_back_and_that_undone(tmp_path: Path) -> None:
    with _service(tmp_path) as (client, board):
        _give(client, FIRST)
        _give(client, SECOND)

        back = client.post("/api/package/rollback").json()
        pin_back = sorted(board.hal.lines)
        again = client.post("/api/package/rollback").json()

    assert (back["running"]["project"], back["previous"]["project"], pin_back) == (
        "First",
        "Second",
        [17],
    )
    assert (again["running"]["project"], again["previous"]["project"]) == ("Second", "First")


def test_a_persistent_variable_keeps_its_value_from_one_package_to_the_next_and_back(
    tmp_path: Path,
) -> None:
    def visits(client: TestClient) -> object:
        return client.get("/api/status").json()["variables"][0]["value"]

    with _service(tmp_path) as (client, _):
        _give(client, FIRST)
        client.put(f"/api/variables/{VISITS}", json={"value": 7})

        _give(client, SECOND)
        forward = visits(client)
        client.put(f"/api/variables/{VISITS}", json={"value": 9})
        client.post("/api/package/rollback")

        assert (forward, visits(client)) == (7, 9)  # a counter does not go back with the lights


def test_the_trace_goes_on_through_an_activation_and_says_what_was_activated(
    tmp_path: Path,
) -> None:
    with _service(tmp_path) as (client, _):
        run = client.get("/api/trace").json()["run"]
        _give(client, FIRST)
        _give(client, SECOND)
        client.post("/api/package/rollback")
        trace = client.get("/api/trace").json()

    kinds = [entry["kind"] for entry in trace["entries"]]
    assert kinds == [
        "service.started",
        "package.stored",
        "package.activated",
        "package.stored",
        "package.activated",
        "package.activated",
    ]
    assert trace["run"] == run
    assert [entry["number"] for entry in trace["entries"]] == [1, 2, 3, 4, 5, 6]
    second, back = trace["entries"][4]["params"], trace["entries"][5]["params"]
    assert second == {"project": "Second", "package": SECOND_HASH, "previous": FIRST_HASH}
    assert back == {
        "project": "First",
        "package": FIRST_HASH,
        "previous": SECOND_HASH,
        "rollback": True,
    }


def test_a_listener_of_the_state_is_told_what_runs_after_an_activation(tmp_path: Path) -> None:
    with _service(tmp_path) as (client, _), client.websocket_connect("/api/ws") as ws:
        empty = ws.receive_json()

        _give(client, FIRST)
        told = ws.receive_json()

    assert (empty["outputs"], [o["name"] for o in told["outputs"]]) == ([], ["LED"])


def test_a_package_is_not_activated_while_panic_is_on(tmp_path: Path) -> None:
    with _service(tmp_path) as (client, board):
        _give(client, FIRST)
        _give(client, SECOND, activate=False)
        client.post("/api/panic")

        refused = client.post("/api/package/activate", json={"hash": SECOND_HASH})
        packages = client.get("/api/package").json()

    assert (refused.status_code, refused.json()["code"]) == (409, "panic.active")
    assert (packages["running"]["project"], len(board.hals)) == ("First", 2)


@pytest.mark.parametrize(
    ("method", "path", "body", "status", "code"),
    [
        ("post", "/api/package/activate", {"hash": SECOND_HASH}, 404, "package.not_stored"),
        ("post", "/api/package/activate", {"hash": "../state"}, 404, "package.not_stored"),
        ("post", "/api/package/rollback", None, 409, "package.no_previous"),
    ],
)
def test_what_cannot_be_activated_is_refused_and_nothing_changes(
    tmp_path: Path, method: str, path: str, body: dict[str, str] | None, status: int, code: str
) -> None:
    with _service(tmp_path) as (client, board):
        _give(client, FIRST)

        refused = client.request(method, path, json=body)
        running = client.get("/api/package").json()["running"]

    assert (refused.status_code, refused.json()["code"]) == (status, code)
    assert (running["project"], len(board.hals)) == ("First", 2)


def test_a_package_that_is_not_one_is_refused_and_nothing_is_kept(tmp_path: Path) -> None:
    with _service(tmp_path) as (client, _):
        _give(client, FIRST)

        refused = client.put("/api/package", content=_bytes({**SECOND, "kind": "nothing"}))
        packages = client.get("/api/package").json()

    assert (refused.status_code, refused.json()["code"]) == (422, "package.invalid")
    assert (packages["staged"], packages["running"]["project"]) == (None, "First")


def test_a_package_too_large_is_refused_by_the_api(tmp_path: Path) -> None:
    with _service(tmp_path) as (client, _):
        refused = client.put("/api/package", content=b" " * (MAX_BYTES + 1))

    assert (refused.status_code, refused.json()["code"]) == (413, "package.too_large")


def test_a_package_that_cannot_be_started_leaves_what_ran_before_running(tmp_path: Path) -> None:
    with _service(tmp_path) as (client, board):
        _give(client, FIRST)
        _give(client, SECOND, activate=False)
        board.fail = True  # the HAL will not open for the new package

        failed = client.post("/api/package/activate", json={"hash": SECOND_HASH})
        packages = client.get("/api/package").json()
        client.post(f"/api/sequences/{ON}/start")
        lit, kinds = board.hal.lines[17].active, _kinds(client)

    assert (failed.status_code, failed.json()["code"]) == (500, "package.activation_failed")
    assert failed.json()["params"] == {"hash": SECOND_HASH, "problem": "hal.chip_not_found"}
    assert (packages["running"]["project"], packages["active"]["project"]) == ("First", "First")
    assert packages["staged"]["project"] == "Second"  # still there, to try again
    assert lit  # and what ran before works
    assert kinds[-2:] == ["package.refused", "sequence.started"]


def test_a_service_that_restarts_runs_the_package_that_was_active(tmp_path: Path) -> None:
    with _service(tmp_path) as (client, _):
        _give(client, FIRST)
        _give(client, SECOND)

    with _service(tmp_path) as (client, board):
        packages = client.get("/api/package").json()
        pins = sorted(board.hal.lines)

    assert (packages["running"]["project"], packages["previous"]["project"], pins) == (
        "Second",
        "First",
        [27],
    )


def test_a_service_whose_active_package_cannot_be_claimed_starts_empty_and_says_why(
    tmp_path: Path,
) -> None:
    """Another program holds a line of the package: the claim fails. The service must still
    start, or systemd would restart it for ever."""
    with _service(tmp_path) as (client, _):
        _give(client, FIRST)

    with _service(tmp_path, fail=True) as (client, _):
        packages = client.get("/api/package").json()
        outputs = _outputs(client)

    assert (packages["running"], outputs) == (None, [])
    assert packages["active"] == {"hash": FIRST_HASH, "project": "First"}
    assert packages["problem"]["code"] == "hal.chip_not_found"


def test_what_the_packages_are_is_told_without_reading_them(tmp_path: Path) -> None:
    """Asked at every look of a page: it must not cost reading and checking three packages
    on the event loop, where panic waits too. Their names are in the state."""
    with _service(tmp_path) as (client, _):
        _give(client, FIRST)
        _give(client, SECOND)
        _give(client, _document("Third", 22), activate=False)
        for file in (tmp_path / DIRECTORY).glob("*.package.json"):
            file.write_bytes(b"not read")

        packages = client.get("/api/package").json()

    names = [packages[which]["project"] for which in ("active", "previous", "staged")]
    assert names == ["Second", "First", "Third"]


def test_checking_a_package_does_not_keep_other_requests_waiting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A large package takes a second to check. Panic, and everything else, must not wait
    behind it: the check is off the event loop."""
    checking, release = threading.Event(), threading.Event()
    check = Deployed.check

    def slow(self: Deployed, content: bytes) -> LoadedPackage:
        checking.set()
        assert release.wait(WAIT_S)
        return check(self, content)

    monkeypatch.setattr(Deployed, "check", slow)
    waiting = ThreadPoolExecutor(max_workers=1)
    try:
        with _service(tmp_path) as (client, _):
            stored = waiting.submit(client.put, "/api/package", content=_bytes(FIRST))
            assert checking.wait(WAIT_S)
            meanwhile = client.post("/api/panic")  # answered while the check goes on
            still_checking = not stored.done()
            release.set()
            answer = stored.result(timeout=WAIT_S)
    finally:
        release.set()
        waiting.shutdown(wait=False)

    assert (meanwhile.status_code, still_checking, answer.status_code) == (200, True, 200)


def test_a_package_is_not_activated_if_the_board_cannot_write_that_it_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A card that went read-only: nothing must change, or the answer would say it failed
    with the new package already running, and a restart would bring the old one back."""
    with _service(tmp_path) as (client, board):
        _give(client, FIRST)
        _give(client, SECOND, activate=False)
        write = deployed.write_whole

        def read_only(path: Path, content: bytes) -> None:
            if path.name == STATE_NAME:
                raise OSError(30, "Read-only file system")
            write(path, content)

        monkeypatch.setattr(deployed, "write_whole", read_only)

        refused = client.post("/api/package/activate", json={"hash": SECOND_HASH})
        packages = client.get("/api/package").json()
        opened, kinds = len(board.hals), _kinds(client)

    assert (refused.status_code, refused.json()["code"]) == (500, "package.unwritable")
    assert (packages["running"]["project"], packages["active"]["project"]) == ("First", "First")
    assert opened == 2  # the HAL of the first package was never closed
    assert "package.activated" not in kinds[3:]


def test_panic_that_comes_while_an_activation_is_under_way_is_not_taken_away_by_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The activation waits for the card (the state is written off the event loop), and
    panic may come meanwhile. The package must not start: its controller would be born
    without panic, and panic is released by a person, not by a package."""
    with _service(tmp_path) as (client, board):
        _give(client, FIRST)
        _give(client, SECOND, activate=False)
        activate = Deployed.activate

        def panic_first(self: Deployed, package: str) -> Pointers:
            assert client.post("/api/panic").status_code == 200  # while the card is written
            return activate(self, package)

        monkeypatch.setattr(Deployed, "activate", panic_first)

        refused = client.post("/api/package/activate", json={"hash": SECOND_HASH})
        state = client.get("/api/status").json()
        packages = client.get("/api/package").json()
        started = client.post(f"/api/sequences/{ON}/start")

    assert (refused.status_code, refused.json()["code"]) == (409, "panic.active")
    assert state["panic"] is True
    assert (packages["running"]["project"], packages["active"]["project"]) == ("First", "First")
    assert (started.status_code, len(board.hals)) == (409, 2)  # still in panic, same HAL


def test_a_listener_of_the_state_is_told_when_an_activation_fails(tmp_path: Path) -> None:
    """Everything stopped and what ran before started again from nothing: whoever shows
    the state must not go on showing the LED on and the sequence running."""
    waiting = ThreadPoolExecutor(max_workers=1)
    try:
        with _service(tmp_path) as (client, board), client.websocket_connect("/api/ws") as ws:
            _give(client, FIRST)
            _give(client, SECOND, activate=False)
            client.post(f"/api/sequences/{ON}/start")
            while not any(s["running"] for s in ws.receive_json()["sequences"]):
                pass  # up to the state with the sequence running
            board.fail = True

            client.post("/api/package/activate", json={"hash": SECOND_HASH})
            told = waiting.submit(ws.receive_json).result(timeout=WAIT_S)
    finally:
        waiting.shutdown(wait=False)

    assert [(o["name"], o["on"]) for o in told["outputs"]] == [("LED", False)]
    assert [s["running"] for s in told["sequences"]] == [False]


def test_what_runs_failing_to_stop_is_not_blamed_on_the_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The HAL of what runs does not close: its outputs are not known to be safe. That is
    said for what it is, and what ran is claimed again, which makes its outputs safe."""
    with _service(tmp_path) as (client, board):
        _give(client, FIRST)
        _give(client, SECOND, activate=False)

        def stuck() -> None:
            raise PrimumError(ErrorCode.HAL_SAFE_STATE_INCOMPLETE, {"pins": (17,)})

        monkeypatch.setattr(board.hal, "close", stuck)

        failed = client.post("/api/package/activate", json={"hash": SECOND_HASH})
        packages = client.get("/api/package").json()
        trace = client.get("/api/trace").json()["entries"]

    assert (failed.status_code, failed.json()["code"]) == (500, "package.stop_failed")
    assert failed.json()["params"] == {"hash": SECOND_HASH, "problem": "hal.safe_state_incomplete"}
    assert (packages["running"]["project"], packages["active"]["project"]) == ("First", "First")
    assert sorted(board.hal.lines) == [17]  # claimed again, on a HAL of its own
    assert (trace[-1]["kind"], trace[-1]["params"]["problem"]) == (
        "package.refused",
        "package.stop_failed",
    )


def test_an_activation_refused_by_panic_is_noted(tmp_path: Path) -> None:
    with _service(tmp_path) as (client, _):
        _give(client, FIRST)
        _give(client, SECOND)
        client.post("/api/panic")

        client.post("/api/package/rollback")
        last = client.get("/api/trace").json()["entries"][-1]

    assert (last["kind"], last["params"]) == (
        "package.refused",
        {"hash": FIRST_HASH, "problem": "panic.active"},
    )


def test_what_a_power_cut_left_half_written_is_dropped(kept: Deployed, tmp_path: Path) -> None:
    (tmp_path / DIRECTORY).mkdir()
    stray = tmp_path / DIRECTORY / "abc.package.tmp"
    stray.write_bytes(b"half a package")

    kept.store(_bytes(FIRST))

    assert not stray.exists()


def test_a_counter_survives_a_package_of_another_project_and_the_way_back(
    tmp_path: Path,
) -> None:
    """Persistent values are the project's: running another project for a while must not
    cost a project its own."""
    other = _document("Other", 22, project=900)

    def visits(client: TestClient) -> object:
        return client.get("/api/status").json()["variables"][0]["value"]

    with _service(tmp_path) as (client, _):
        _give(client, FIRST)
        client.put(f"/api/variables/{VISITS}", json={"value": 3})
        _give(client, other)
        elsewhere = visits(client)
        client.put(f"/api/variables/{VISITS}", json={"value": 8})

        client.post("/api/package/rollback")
        back = visits(client)
        client.post("/api/package/rollback")

        assert (elsewhere, back, visits(client)) == (0, 3, 8)


def test_a_sequence_running_when_a_package_is_activated_is_noted_as_stopped(
    tmp_path: Path,
) -> None:
    with _service(tmp_path) as (client, _):
        _give(client, FIRST)
        client.post(f"/api/sequences/{ON}/start")

        _give(client, SECOND)
        trace = client.get("/api/trace").json()["entries"]

    kinds = [entry["kind"] for entry in trace]
    stopped = next(entry for entry in trace if entry["kind"] == "sequence.stopped")
    assert kinds[-4:] == [
        "sequence.started",
        "package.stored",
        "sequence.stopped",
        "package.activated",
    ]
    assert (stopped["params"]["name"], stopped["params"]["by"]) == ("On", "package")


def test_a_service_whose_active_package_no_longer_reads_starts_empty_and_says_why(
    tmp_path: Path,
) -> None:
    with _service(tmp_path) as (client, _):
        _give(client, FIRST)
    file = tmp_path / DIRECTORY / (FIRST_HASH.removeprefix("sha256:") + ".package.json")
    file.write_bytes(b"\xff not a package")

    with _service(tmp_path) as (client, _):
        packages = client.get("/api/package").json()
        outputs = _outputs(client)
        _give(client, SECOND)  # and it can be given another
        after = client.get("/api/package").json()

    assert (packages["running"], outputs) == (None, [])
    assert packages["active"] == {"hash": FIRST_HASH, "project": "First"}
    assert packages["problem"]["code"] == "package.invalid"
    assert (after["running"]["project"], after["problem"]) == ("Second", None)
    # Where the board keeps its files is not for a client: it is in the service's log.
    assert "path" not in packages["problem"]["params"]
    assert str(tmp_path) not in json.dumps(packages)


def test_every_state_has_a_number_above_the_one_before_also_after_an_activation(
    tmp_path: Path,
) -> None:
    """Two states reach a device by two ways (the answer to a command, the WebSocket) and
    may cross: the number says which is the later one, whatever package it is of."""
    with _service(tmp_path) as (client, _), client.websocket_connect("/api/ws") as ws:
        numbers = [ws.receive_json()["revision"]]
        _give(client, FIRST)
        numbers.append(client.post(f"/api/sequences/{ON}/start").json()["revision"])
        numbers.append(client.get("/api/status").json()["revision"])
        _give(client, SECOND)  # a new controller
        numbers.append(client.get("/api/status").json()["revision"])
        numbers.append(client.post("/api/panic").json()["revision"])

    assert numbers == sorted(set(numbers))


def test_a_service_told_what_to_drive_takes_no_packages(tmp_path: Path) -> None:
    with _service(tmp_path, "--pin", "17") as (client, _):
        packages = client.get("/api/package").json()
        stored = client.put("/api/package", content=_bytes(FIRST))
        activated = client.post("/api/package/activate", json={"hash": FIRST_HASH})

    assert (packages["fixed"], packages["running"]) == (True, None)
    assert (stored.status_code, stored.json()["code"]) == (409, "package.fixed")
    assert (activated.status_code, activated.json()["code"]) == (409, "package.fixed")
