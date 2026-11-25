"""Pairing: the board's code, the devices paired with it, and an API that shows and takes
nothing from anyone else."""

import stat
from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient
from starlette.routing import BaseRoute, Mount
from starlette.websockets import WebSocketDisconnect

from primum_runtime import pairing_tool
from primum_runtime.api import create_app
from primum_runtime.api.pairing import COOKIE
from primum_runtime.config import parse_config
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.pairing import LOCK_S, MAX_ATTEMPTS, MAX_LOCK_S, NAME, Pairing

PIN = 17


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


@pytest.fixture
def pairing(tmp_path: Path, clock: _Clock) -> Pairing:
    return Pairing(tmp_path, clock)


def _wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


# --- The store ---------------------------------------------------------------------------


def test_a_board_makes_its_code_once_and_keeps_it(tmp_path: Path, clock: _Clock) -> None:
    code = Pairing(tmp_path, clock).code()

    assert (len(code), code.isdecimal()) == (6, True)
    assert Pairing(tmp_path, clock).code() == code


def test_only_its_owner_reads_what_is_kept(pairing: Pairing, tmp_path: Path) -> None:
    pairing.pair(pairing.code(), "phone")

    assert stat.S_IMODE((tmp_path / NAME).stat().st_mode) == 0o600


def test_the_token_of_a_device_is_never_kept(pairing: Pairing, tmp_path: Path) -> None:
    device, token = pairing.pair(pairing.code(), "phone")

    assert token not in (tmp_path / NAME).read_text()
    assert pairing.device(token) == device
    assert pairing.device(token + "x") is None


def test_a_wrong_code_pairs_nothing_and_says_how_many_tries_are_left(pairing: Pairing) -> None:
    with pytest.raises(PrimumError) as refused:
        pairing.pair(_wrong(pairing.code()), "phone")

    assert refused.value.code is ErrorCode.PAIRING_CODE_WRONG
    assert refused.value.params == {"left": MAX_ATTEMPTS - 1}
    assert pairing.devices() == ()


def test_after_too_many_wrong_codes_not_even_the_right_one_is_taken_for_a_while(
    pairing: Pairing, clock: _Clock
) -> None:
    code = pairing.code()
    for _ in range(MAX_ATTEMPTS):
        with pytest.raises(PrimumError):
            pairing.pair(_wrong(code), "phone")

    with pytest.raises(PrimumError) as locked:
        pairing.pair(code, "phone")
    clock.now = LOCK_S + 1
    device, _ = pairing.pair(code, "phone")

    assert locked.value.code is ErrorCode.PAIRING_LOCKED
    assert locked.value.params == {"seconds": int(LOCK_S)}
    assert pairing.devices() == (device,)


def _lock(pairing: Pairing, clock: _Clock) -> int:
    """Wait out any lock, then give wrong codes until none is taken: for how long."""
    wrong = _wrong(pairing.code())
    while True:
        try:
            pairing.pair(wrong, "phone")
        except PrimumError as error:
            if error.code is ErrorCode.PAIRING_LOCKED:
                seconds = error.params["seconds"]
                assert isinstance(seconds, int)
                clock.now += seconds
                return seconds


def test_each_lock_in_a_row_lasts_twice_the_one_before_up_to_a_day(
    pairing: Pairing, clock: _Clock
) -> None:
    """A fixed wait lets a patient program try every code in under two years."""
    waits = [_lock(pairing, clock) for _ in range(12)]

    assert waits[:4] == [300, 600, 1200, 2400]
    assert waits[-2:] == [MAX_LOCK_S, MAX_LOCK_S]


def test_a_right_code_sets_the_wait_back_to_the_shortest(pairing: Pairing, clock: _Clock) -> None:
    for _ in range(3):
        _lock(pairing, clock)

    pairing.pair(pairing.code(), "phone")

    assert _lock(pairing, clock) == 300


def test_a_right_code_forgets_the_wrong_ones_before_it(pairing: Pairing) -> None:
    code = pairing.code()
    for _ in range(MAX_ATTEMPTS - 1):
        with pytest.raises(PrimumError):
            pairing.pair(_wrong(code), "phone")
    pairing.pair(code, "phone")

    with pytest.raises(PrimumError) as refused:
        pairing.pair(_wrong(code), "phone")

    assert refused.value.params == {"left": MAX_ATTEMPTS - 1}


def test_a_device_that_is_forgotten_is_no_longer_known(pairing: Pairing) -> None:
    first, first_token = pairing.pair(pairing.code(), "phone")
    second, second_token = pairing.pair(pairing.code(), "laptop")

    pairing.forget(first.id)

    assert (pairing.device(first_token), pairing.device(second_token)) == (None, second)
    with pytest.raises(PrimumError) as unknown:
        pairing.forget(first.id)
    assert unknown.value.code is ErrorCode.PAIRING_DEVICE_UNKNOWN


def test_renewing_the_code_forgets_every_device(pairing: Pairing) -> None:
    code = pairing.code()
    _, token = pairing.pair(code, "phone")

    renewed = pairing.renew()

    assert pairing.device(token) is None
    assert pairing.code() == renewed
    assert pairing.pair(renewed, "phone")[0] in pairing.devices()


@pytest.mark.parametrize("content", ["{", "[]", '{"code": "12", "devices": []}', '{"code": 5}'])
def test_a_file_that_does_not_say_what_it_should_pairs_nobody(
    pairing: Pairing, tmp_path: Path, content: str
) -> None:
    (tmp_path / NAME).write_text(content)

    assert pairing.devices() == ()
    assert len(pairing.code()) == 6  # a new one


def test_a_file_that_cannot_be_read_is_left_as_it_is(
    pairing: Pairing, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not being able to read it does not mean there is nothing in it: taking it for
    missing would let anyone, with any wrong code, forget every device and change the code."""
    _, token = pairing.pair(pairing.code(), "phone")
    before = (tmp_path / NAME).read_bytes()

    def denied(_self: Path, encoding: str | None = None) -> str:
        raise PermissionError(13, "Permission denied")

    with monkeypatch.context() as patched:
        patched.setattr(Path, "read_text", denied)
        refused: list[ErrorCode] = []
        for ask in (
            lambda: pairing.pair("000000", "x"),
            pairing.code,
            lambda: pairing.device(token),
        ):
            with pytest.raises(PrimumError) as error:
                ask()
            refused.append(error.value.code)

    assert refused == [ErrorCode.PAIRING_UNREADABLE] * 3
    assert (tmp_path / NAME).read_bytes() == before
    assert pairing.device(token) is not None


def test_a_code_that_cannot_be_kept_is_an_error_with_a_code(tmp_path: Path, clock: _Clock) -> None:
    (tmp_path / "file").write_text("")

    with pytest.raises(PrimumError) as error:
        Pairing(tmp_path / "file", clock).code()

    assert error.value.code is ErrorCode.PAIRING_UNWRITABLE


def test_a_file_written_by_another_user_is_handed_to_the_owner_of_the_data(
    pairing: Pairing, monkeypatch: pytest.MonkeyPatch
) -> None:
    """root runs ``primum-pairing --renew``: the service must still read its file."""
    handed: list[tuple[int, int]] = []
    monkeypatch.setattr("os.geteuid", lambda: 4242)  # not the owner of the directory

    def hand(_path: Path, uid: int, gid: int) -> None:
        handed.append((uid, gid))

    monkeypatch.setattr("os.chown", hand)

    pairing.renew()

    assert len(handed) == 1


# --- The command -------------------------------------------------------------------------


def test_the_command_shows_the_code_and_renews_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], clock: _Clock
) -> None:
    code = Pairing(tmp_path, clock).code()

    shown = pairing_tool.main(["--data-dir", str(tmp_path)])
    first = capsys.readouterr().out
    renewed = pairing_tool.main(["--data-dir", str(tmp_path), "--renew"])
    second = capsys.readouterr().out.strip()

    assert (shown, first, renewed) == (0, code + "\n", 0)
    assert second != code
    assert Pairing(tmp_path, clock).code() == second


# --- The API -----------------------------------------------------------------------------


@contextmanager
def _service(data_dir: Path, *options: str) -> Generator[TestClient]:
    arguments = ["--simulate", "--pin", str(PIN), "--data-dir", str(data_dir), *options]
    with TestClient(create_app(parse_config(arguments, {}))) as client:
        yield client


def _pair(client: TestClient, data_dir: Path, name: str = "phone") -> tuple[str, str]:
    """Pair ``client`` with the board's code: its token and the id of its device."""
    code = Pairing(data_dir, lambda: 0.0).code()
    response = client.post("/api/pairing", json={"code": code, "name": name})
    assert response.status_code == 200
    token: str = response.json()["token"]
    device: str = response.json()["device"]["id"]
    return token, device


OPEN_TO_ALL = {("GET", "/api/pairing"), ("POST", "/api/pairing")}


def _routes(routes: Sequence[BaseRoute]) -> Iterator[BaseRoute]:
    """Every route of the app, those of the routers it includes too. One of a kind this
    does not know fails the test: it must be looked at, not skipped."""
    for route in routes:
        included: APIRouter | None = getattr(route, "original_router", None)
        if included is not None:
            yield from _routes(included.routes)
        elif isinstance(route, APIRoute | APIWebSocketRoute):
            yield route
        else:
            assert isinstance(route, Mount), route  # the web UI's files
            assert route.path == "", route


def _asked(path: str) -> str:
    """``/api/outputs/{output_id}`` → ``/api/outputs/x``."""
    return "/".join("x" if part.startswith("{") else part for part in path.split("/"))


def test_nothing_is_shown_or_taken_from_a_device_that_is_not_paired(tmp_path: Path) -> None:
    """Every route the app has, found by walking it: a new one that is not behind pairing
    fails here without anyone listing it."""
    answers: dict[tuple[str, str], tuple[int, object]] = {}
    with _service(tmp_path) as client:
        app = client.app
        assert isinstance(app, FastAPI)
        for route in _routes(app.routes):
            if not isinstance(route, APIRoute):
                continue
            for method in sorted((route.methods or set()) - {"HEAD"}):
                if (method, route.path) not in OPEN_TO_ALL:
                    answer = client.request(method, _asked(route.path), json={"action": "on"})
                    answers[method, route.path] = (answer.status_code, answer.json())

    assert len(answers) > 10  # the walk found them
    refused: tuple[int, object] = (401, {"code": "pairing.required", "params": {}})
    assert {route: answer for route, answer in answers.items() if answer != refused} == {}


def test_a_websocket_is_not_opened_for_a_device_that_is_not_paired(tmp_path: Path) -> None:
    closed: dict[str, int] = {}
    with _service(tmp_path) as client:
        app = client.app
        assert isinstance(app, FastAPI)
        for route in _routes(app.routes):
            if isinstance(route, APIWebSocketRoute):
                with (
                    pytest.raises(WebSocketDisconnect) as refused,
                    client.websocket_connect(route.path),
                ):
                    pass
                closed[route.path] = refused.value.code

    assert closed == {"/api/ws": 1008, "/api/trace/ws": 1008}


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_the_service_describes_its_api_to_nobody(tmp_path: Path, path: str) -> None:
    with _service(tmp_path) as client:
        assert client.get(path).status_code == 404


def test_anyone_may_ask_whether_they_are_paired(tmp_path: Path) -> None:
    with _service(tmp_path) as client:
        asked = client.get("/api/pairing")

    assert asked.json() == {"required": True, "device": None}


def test_a_device_that_gives_the_code_is_paired_by_its_cookie(tmp_path: Path) -> None:
    with _service(tmp_path) as client:
        token, _ = _pair(client, tmp_path)
        cookie = client.cookies.get(COOKIE)
        status = client.get("/api/status")
        asked = client.get("/api/pairing").json()
        with client.websocket_connect("/api/ws") as ws:
            state = ws.receive_json()

    assert cookie == token
    assert status.status_code == 200
    assert asked["device"] == {**asked["device"], "name": "phone", "current": True}
    assert [output["name"] for output in state["outputs"]] == ["led"]


def test_the_cookie_is_not_for_the_page_code_nor_for_other_sites(tmp_path: Path) -> None:
    with _service(tmp_path) as client:
        code = Pairing(tmp_path, lambda: 0.0).code()
        header = client.post("/api/pairing", json={"code": code}).headers["set-cookie"].lower()

    assert "httponly" in header
    assert "samesite=strict" in header


def test_a_program_is_paired_by_its_bearer_token(tmp_path: Path) -> None:
    with _service(tmp_path) as client:
        token, _ = _pair(client, tmp_path)
        client.cookies.clear()
        without = client.get("/api/status")
        bearer = {"Authorization": f"Bearer {token}"}
        with_token = client.get("/api/status", headers=bearer)
        wrong = client.get("/api/status", headers={"Authorization": "Bearer nothing"})
        with client.websocket_connect("/api/ws", headers=bearer) as ws:
            state = ws.receive_json()

    assert (without.status_code, with_token.status_code, wrong.status_code) == (401, 200, 401)
    assert "outputs" in state


def test_a_wrong_code_is_refused_and_too_many_are_made_to_wait(tmp_path: Path) -> None:
    with _service(tmp_path) as client:
        wrong = {"code": _wrong(Pairing(tmp_path, lambda: 0.0).code())}
        answers = [client.post("/api/pairing", json=wrong) for _ in range(MAX_ATTEMPTS + 1)]

    assert (answers[0].status_code, answers[0].json()["code"]) == (403, "pairing.code_wrong")
    assert answers[0].json()["params"] == {"left": MAX_ATTEMPTS - 1}
    assert [(a.status_code, a.json()["code"]) for a in answers[-2:]] == [
        (429, "pairing.locked"),
        (429, "pairing.locked"),
    ]
    assert COOKIE not in client.cookies


def test_a_device_unpairs_itself(tmp_path: Path) -> None:
    with _service(tmp_path) as client:
        _pair(client, tmp_path)

        gone = client.delete("/api/pairing")
        after = client.get("/api/status")

    assert (gone.status_code, gone.json()) == (200, {"required": True, "device": None})
    assert after.status_code == 401


def test_a_paired_device_lists_the_others_and_forgets_one(tmp_path: Path) -> None:
    with _service(tmp_path) as client:
        lost_token, lost = _pair(client, tmp_path, "lost phone")
        client.cookies.clear()
        _pair(client, tmp_path, "laptop")

        listed = client.get("/api/pairing/devices").json()
        left = client.delete(f"/api/pairing/devices/{lost}").json()
        unknown = client.delete("/api/pairing/devices/nobody")
        with_lost = client.get("/api/status", headers={"Authorization": f"Bearer {lost_token}"})

    assert [(d["name"], d["current"]) for d in listed] == [("lost phone", False), ("laptop", True)]
    assert [d["name"] for d in left] == ["laptop"]
    assert (unknown.status_code, unknown.json()["code"]) == (404, "pairing.device_unknown")
    assert with_lost.status_code == 401


def test_a_code_renewed_from_the_board_unpairs_a_running_service(tmp_path: Path) -> None:
    with _service(tmp_path) as client:
        _pair(client, tmp_path)

        pairing_tool.main(["--data-dir", str(tmp_path), "--renew"])
        after = client.get("/api/status")

    assert after.status_code == 401


def test_a_service_without_pairing_asks_for_nothing_and_says_so(tmp_path: Path) -> None:
    with _service(tmp_path, "--no-pairing") as client:
        status = client.get("/api/status")
        asked = client.get("/api/pairing")
        pair = client.post("/api/pairing", json={"code": "123456"})

    assert status.status_code == 200
    assert asked.json() == {"required": False, "device": None}
    assert (pair.status_code, pair.json()["code"]) == (409, "pairing.off")
    assert not (tmp_path / NAME).exists()


def test_pairing_is_on_unless_the_service_is_told_otherwise() -> None:
    assert parse_config(["--simulate", "--pin", "17"], {}).pairing is True
    assert parse_config(["--simulate", "--pin", "17", "--no-pairing"], {}).pairing is False
    assert parse_config(["--simulate", "--pin", "17"], {"PRIMUM_NO_PAIRING": "1"}).pairing is False


def test_an_error_never_tells_a_client_where_the_board_keeps_its_files(tmp_path: Path) -> None:
    (tmp_path / "file").write_text("")

    with _service(tmp_path / "file") as client:
        failed = client.post("/api/pairing", json={"code": "123456"})

    assert (failed.status_code, failed.json()["code"]) == (500, "pairing.unwritable")
    assert "path" not in failed.json()["params"]
    assert str(tmp_path) not in failed.text


def test_the_command_says_to_run_it_as_root_and_shows_no_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, clock: _Clock
) -> None:
    Pairing(tmp_path, clock).code()

    def denied(_self: Path, encoding: str | None = None) -> str:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_text", denied)
    monkeypatch.setattr("os.geteuid", lambda: 1000)

    status = pairing_tool.main(["--data-dir", str(tmp_path)])

    assert status == 1
    assert [record.exc_info for record in caplog.records] == [None]
    assert "sudo" in caplog.records[0].getMessage()


@pytest.mark.parametrize(
    ("origin", "taken"),
    [
        (None, True),  # a program
        ("http://testserver", True),  # the page itself
        ("http://testserver:9000", False),  # another service of the same host
        ("http://elsewhere.example", False),
    ],
)
def test_a_page_of_another_origin_cannot_use_the_cookie_of_a_paired_browser(
    tmp_path: Path, origin: str | None, taken: bool
) -> None:
    """``SameSite`` tells sites apart, not ports: a page served from another port of the
    board would be sent the cookie. A browser says where a request comes from."""
    headers = {} if origin is None else {"Origin": origin}
    with _service(tmp_path) as client:
        _pair(client, tmp_path)

        panic = client.post("/api/panic", headers=headers)
        try:
            with client.websocket_connect("/api/ws", headers=headers) as ws:
                ws.receive_json()
            opened = True
        except WebSocketDisconnect:
            opened = False

    assert (panic.status_code == 200, opened) == (taken, taken)
    if not taken:
        assert panic.json()["code"] == "request.origin_refused"
