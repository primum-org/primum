"""The HTTP API and the WebSocket, through FastAPI's test client and the simulated HAL."""

import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from primum_runtime import declared
from primum_runtime.api import create_app
from primum_runtime.board import load_board
from primum_runtime.config import BUTTON, LED, RuntimeConfig, parse_config
from primum_runtime.declared import Declaration
from primum_runtime.errors import PrimumError
from primum_runtime.hal import Claim, OutputSpec, SimulatedHal

BOARD = load_board("rpi4b")

PIN = 17
BUTTON_PIN = 22
CONFIG = parse_config(["--simulate", "--pin", str(PIN)], {})
WITH_BUTTON = parse_config(
    [*("--simulate", "--pin", str(PIN)), *("--input-pin", str(BUTTON_PIN), "--input-pull", "up")],
    {},
)
OFF = {"outputs": [{"name": LED, "on": False}], "inputs": [], "panic": False}
ON = {"outputs": [{"name": LED, "on": True}], "inputs": [], "panic": False}


@pytest.fixture
def hal() -> SimulatedHal:
    return SimulatedHal(BOARD)


@pytest.fixture
def client(hal: SimulatedHal) -> Iterator[TestClient]:
    with TestClient(create_app(CONFIG, open_hal=lambda: hal)) as client:
        yield client


def test_status_reports_every_output_off_after_start(client: TestClient) -> None:
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json() == OFF


def test_put_output_turns_the_line_on_and_returns_the_new_state(
    client: TestClient, hal: SimulatedHal
) -> None:
    response = client.put(f"/api/outputs/{LED}", json={"on": True})

    assert response.json() == ON
    assert hal.lines[PIN].active


def test_unknown_output_is_404_with_its_code(client: TestClient) -> None:
    response = client.put("/api/outputs/fan", json={"on": True})

    assert response.status_code == 404
    assert response.json() == {"code": "output.unknown", "params": {"name": "fan"}}


@pytest.mark.parametrize("body", [{"on": "yes"}, {"on": 1}, {}, {"on": True, "blink": True}])
def test_invalid_body_is_422_request_invalid(client: TestClient, body: dict[str, object]) -> None:
    response = client.put(f"/api/outputs/{LED}", json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "request.invalid"


def test_invalid_body_names_the_field_and_never_a_source_file(client: TestClient) -> None:
    response = client.put(f"/api/outputs/{LED}", json={"on": "yes"})

    params = response.json()["params"]
    assert params["fields"] == ["body.on"]
    assert params["detail"].startswith("body.on: ")
    assert ".py" not in params["detail"]


def test_unknown_api_path_is_404_request_not_found(client: TestClient) -> None:
    response = client.get("/api/nothing")

    assert response.status_code == 404
    assert response.json() == {"code": "request.not_found", "params": {"path": "/api/nothing"}}


def test_wrong_method_is_405_request_method_not_allowed(client: TestClient) -> None:
    response = client.post("/api/status")

    assert response.status_code == 405
    assert response.json()["code"] == "request.method_not_allowed"


def test_panic_turns_off_and_refuses_commands_until_released(
    client: TestClient, hal: SimulatedHal
) -> None:
    client.put(f"/api/outputs/{LED}", json={"on": True})

    panicked = client.post("/api/panic")
    refused = client.put(f"/api/outputs/{LED}", json={"on": True})
    released = client.delete("/api/panic")

    assert panicked.json() == {**OFF, "panic": True}
    assert not hal.lines[PIN].active
    assert refused.status_code == 409
    assert refused.json() == {"code": "panic.active", "params": {}}
    assert released.json() == OFF


def test_websocket_sends_the_current_state_then_every_change(client: TestClient) -> None:
    with client.websocket_connect("/api/ws") as websocket:
        first = websocket.receive_json()
        client.put(f"/api/outputs/{LED}", json={"on": True})
        second = websocket.receive_json()
        client.post("/api/panic")
        third = websocket.receive_json()

    assert first == OFF
    assert second == ON
    assert third == {**OFF, "panic": True}


def _with_button(hal: SimulatedHal) -> TestClient:
    return TestClient(create_app(WITH_BUTTON, open_hal=lambda: hal))


def test_status_reports_the_inputs_too(hal: SimulatedHal) -> None:
    with _with_button(hal) as client:
        assert client.get("/api/status").json()["inputs"] == [{"name": BUTTON, "active": False}]


def test_a_change_of_an_input_reaches_the_websocket_without_anyone_asking(
    hal: SimulatedHal,
) -> None:
    """The event loop watches the HAL's descriptor: nothing polls and no request is made."""
    with _with_button(hal) as client, client.websocket_connect("/api/ws") as websocket:
        websocket.receive_json()

        hal.simulate_input(BUTTON_PIN, True)
        pressed = websocket.receive_json()
        hal.simulate_input(BUTTON_PIN, False)
        released = websocket.receive_json()

    assert pressed["inputs"] == [{"name": BUTTON, "active": True}]
    assert released["inputs"] == [{"name": BUTTON, "active": False}]


def test_a_failure_reading_the_inputs_stops_the_watch_instead_of_spinning(
    hal: SimulatedHal, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The descriptor stays readable when reading fails, so the loop would call again at
    once, for ever. The watch ends, the failure is logged and the service goes on."""
    calls: list[int] = []

    def broken() -> list[object]:
        calls.append(1)
        raise OSError(5, "I/O error")

    with _with_button(hal) as client:
        monkeypatch.setattr(hal, "_read_events", broken)
        hal.simulate_input(BUTTON_PIN, True)

        assert client.get("/api/status").status_code == 200
        assert client.get("/api/status").status_code == 200

    assert calls == [1]
    assert "inputs are no longer listened to" in caplog.text


def test_a_service_without_inputs_watches_nothing(hal: SimulatedHal) -> None:
    with TestClient(create_app(CONFIG, open_hal=lambda: hal)):
        assert hal.events_fd() is None


def test_a_line_that_does_not_follow_is_an_error_with_its_code(
    client: TestClient, hal: SimulatedHal
) -> None:
    hal.lines[PIN].stick(False)

    response = client.put(f"/api/outputs/{LED}", json={"on": True})

    assert response.status_code == 500
    assert response.json() == {
        "code": "element.level_not_reached",
        "params": {"element": LED, "level": 100, "read": 0.0},
    }
    assert client.get("/api/status").json() == OFF  # what it reads, not what was asked


def test_stopping_the_service_applies_the_safe_state_and_releases_the_line(
    hal: SimulatedHal,
) -> None:
    app = create_app(CONFIG, open_hal=lambda: hal)
    with TestClient(app) as client:
        client.put(f"/api/outputs/{LED}", json={"on": True})
        line = hal.lines[PIN]

    assert not line.active
    assert line.released
    assert app.state.stopped_safely


def test_root_serves_the_page(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'src="app.js"' in response.text


@pytest.mark.parametrize(
    "path",
    [
        "app.js",
        "i18n.js",
        "icons.js",
        "app.css",
        "generated/tokens.css",
        "generated/i18n/es.json",
        "generated/icons/s-warn.svg",
    ],
)
def test_the_page_assets_are_served(client: TestClient, path: str) -> None:
    assert client.get(f"/{path}").status_code == 200


# --- what a real service declares, and what it tells systemd -------------------------------


def _real(tmp_path: Path) -> RuntimeConfig:
    """The configuration of a service on a board, not simulated; the tests give it a HAL."""
    return parse_config(["--pin", str(PIN), "--data-dir", str(tmp_path)], {})


def test_a_service_declares_its_outputs_while_it_runs_and_forgets_them_once_stopped(
    hal: SimulatedHal, tmp_path: Path
) -> None:
    with TestClient(create_app(_real(tmp_path), open_hal=lambda: hal, env={})):
        running = declared.read(tmp_path)

    assert running == Declaration("rpi4b", (OutputSpec(pin=PIN, active_low=False),))
    assert declared.read(tmp_path) is None


def test_the_outputs_are_declared_before_they_are_claimed(tmp_path: Path) -> None:
    seen: list[Declaration | None] = []

    class Watching(SimulatedHal):
        def claim(self, claim: Claim) -> None:
            seen.append(declared.read(tmp_path))
            super().claim(claim)

    with TestClient(create_app(_real(tmp_path), open_hal=lambda: Watching(BOARD), env={})):
        pass

    assert seen == [Declaration("rpi4b", (OutputSpec(pin=PIN, active_low=False),))]


def test_a_service_that_cannot_declare_its_outputs_does_not_claim_them(
    hal: SimulatedHal, tmp_path: Path
) -> None:
    config = _real(tmp_path / "nowhere")

    with pytest.raises(PrimumError) as raised, TestClient(create_app(config, lambda: hal, {})):
        pass

    assert raised.value.code == "safe.declaration_unwritable"
    assert hal.lines == {}


def test_a_stop_that_leaves_an_output_unsafe_keeps_it_declared(
    hal: SimulatedHal, tmp_path: Path
) -> None:
    app = create_app(_real(tmp_path), open_hal=lambda: hal, env={})

    with pytest.raises(PrimumError), TestClient(app):
        hal.lines[PIN].stick(True)

    assert declared.read(tmp_path) is not None
    assert not app.state.stopped_safely


def test_a_simulated_service_declares_nothing(hal: SimulatedHal, tmp_path: Path) -> None:
    config = parse_config(["--simulate", "--pin", str(PIN), "--data-dir", str(tmp_path)], {})

    with TestClient(create_app(config, open_hal=lambda: hal, env={})):
        assert list(tmp_path.iterdir()) == []


def test_systemd_is_told_when_the_service_is_ready_and_when_it_stops(
    hal: SimulatedHal, tmp_path: Path
) -> None:
    address = tmp_path / "notify"
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as listener:
        listener.bind(str(address))
        listener.setblocking(False)
        env = {"NOTIFY_SOCKET": str(address), "WATCHDOG_USEC": "10000000"}

        with TestClient(create_app(CONFIG, open_hal=lambda: hal, env=env)):
            started = [listener.recv(64), listener.recv(64)]
        stopped = listener.recv(64)

    # Ready, and the first beat of the watchdog at once: the next comes five seconds later.
    assert sorted(started) == [b"READY=1", b"WATCHDOG=1"]
    assert stopped == b"STOPPING=1"
