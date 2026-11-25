"""Pairing: the board's code, the devices paired with it, and an API that shows and takes
nothing from anyone else."""

import stat
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from primum_runtime import pairing_tool
from primum_runtime.api import create_app
from primum_runtime.api.pairing import COOKIE
from primum_runtime.config import parse_config
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.pairing import LOCK_S, MAX_ATTEMPTS, NAME, Pairing

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


REQUESTS = [
    ("GET", "/api/status"),
    ("PUT", "/api/outputs/led"),
    ("DELETE", "/api/outputs/led"),
    ("POST", "/api/sequences/x/start"),
    ("POST", "/api/sequences/x/stop"),
    ("PUT", "/api/variables/x"),
    ("POST", "/api/events/x/fire"),
    ("POST", "/api/panic"),
    ("DELETE", "/api/panic"),
    ("GET", "/api/package"),
    ("PUT", "/api/package"),
    ("POST", "/api/package/activate"),
    ("POST", "/api/package/rollback"),
    ("GET", "/api/trace"),
    ("DELETE", "/api/pairing"),
    ("GET", "/api/pairing/devices"),
    ("DELETE", "/api/pairing/devices/x"),
]


@pytest.mark.parametrize(("method", "path"), REQUESTS)
def test_nothing_is_shown_or_taken_from_a_device_that_is_not_paired(
    tmp_path: Path, method: str, path: str
) -> None:
    with _service(tmp_path) as client:
        refused = client.request(method, path, json={"action": "on"})

    assert (refused.status_code, refused.json()) == (
        401,
        {"code": "pairing.required", "params": {}},
    )


def test_no_route_of_the_api_is_left_out_of_the_list_above() -> None:
    """A new route is behind pairing because the router is; this keeps the list honest."""
    app = create_app(parse_config(["--simulate", "--pin", str(PIN)], {}))
    paths: dict[str, dict[str, object]] = app.openapi()["paths"]
    routes = {
        (method.upper(), _unnamed(path)) for path, methods in paths.items() for method in methods
    }
    open_to_all = {("GET", "/api/pairing"), ("POST", "/api/pairing")}
    listed = {
        (method, path.replace("/x", "/{}").replace("/led", "/{}")) for method, path in REQUESTS
    }

    assert routes - open_to_all == listed


def _unnamed(path: str) -> str:
    """``/api/outputs/{output_id}`` → ``/api/outputs/{}``."""
    parts = ["{}" if part.startswith("{") else part for part in path.split("/")]
    return "/".join(parts)


@pytest.mark.parametrize("path", ["/api/ws", "/api/trace/ws"])
def test_a_websocket_is_not_opened_for_a_device_that_is_not_paired(
    tmp_path: Path, path: str
) -> None:
    with (
        _service(tmp_path) as client,
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect(path),
    ):
        pass

    assert closed.value.code == 1008


def test_the_page_is_served_to_anyone_and_asks_whether_it_is_paired(tmp_path: Path) -> None:
    with _service(tmp_path) as client:
        page = client.get("/")
        asked = client.get("/api/pairing")

    assert page.status_code == 200
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
