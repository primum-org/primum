"""The HTTP API and the WebSocket, through FastAPI's test client and the simulated HAL."""

import socket
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from primum_runtime import declared
from primum_runtime.api import create_app
from primum_runtime.board import load_board
from primum_runtime.config import BUTTON, DIMMER, LED, RuntimeConfig, parse_config
from primum_runtime.declared import Declaration
from primum_runtime.drivers import ElementConfig
from primum_runtime.errors import PrimumError
from primum_runtime.hal import Claim, OutputSpec, PwmSpec, SimulatedHal

BOARD = load_board("rpi4b")

PIN = 17
EXPIRY_WAIT_S = 5  # for a test of one second to expire: far more than it takes
BUTTON_PIN = 22
CONFIG = parse_config(["--simulate", "--no-pairing", "--pin", str(PIN)], {})
WITH_BUTTON = parse_config(
    [
        *("--simulate", "--no-pairing", "--pin", str(PIN)),
        *("--input-pin", str(BUTTON_PIN), "--input-pull", "up"),
    ],
    {},
)
SWITCH = ["on", "off"]
OFF = {
    "outputs": [
        {
            "id": LED,
            "name": LED,
            "on": False,
            "level": 0,
            "actions": SWITCH,
            "remainingMs": None,
            "restFailed": False,
            "controlledBy": None,
        }
    ],
    "inputs": [],
    "panic": False,
    "sequences": [],
    "variables": [],
    "events": [],
    "automations": [],
    "schedules": [],
    "timeKnown": False,
    "variablesUnsaved": False,
}
ON = {
    "outputs": [
        {
            "id": LED,
            "name": LED,
            "on": True,
            "level": 100,
            "actions": SWITCH,
            "remainingMs": None,
            "restFailed": False,
            "controlledBy": "manual",
        }
    ],
    "inputs": [],
    "panic": False,
    "sequences": [],
    "variables": [],
    "events": [],
    "automations": [],
    "schedules": [],
    "timeKnown": False,
    "variablesUnsaved": False,
}


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
    response = client.put(f"/api/outputs/{LED}", json={"action": "on"})

    assert response.json() == ON
    assert hal.lines[PIN].active


def test_unknown_output_is_404_with_its_code(client: TestClient) -> None:
    response = client.put("/api/outputs/fan", json={"action": "on"})

    assert response.status_code == 404
    assert response.json() == {"code": "output.unknown", "params": {"name": "fan"}}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"on": True},
        {"action": 1},
        {"action": "on", "blink": True},
        {"action": "on", "arguments": [40]},
        {"action": "on", "arguments": {"level": [40]}},
    ],
)
def test_invalid_body_is_422_request_invalid(client: TestClient, body: dict[str, object]) -> None:
    response = client.put(f"/api/outputs/{LED}", json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "request.invalid"


def test_invalid_body_names_the_field_and_never_a_source_file(client: TestClient) -> None:
    response = client.put(f"/api/outputs/{LED}", json={"action": 1})

    params = response.json()["params"]
    assert params["fields"] == ["body.action"]
    assert params["detail"].startswith("body.action: ")
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
    client.put(f"/api/outputs/{LED}", json={"action": "on"})

    panicked = client.post("/api/panic")
    refused = client.put(f"/api/outputs/{LED}", json={"action": "on"})
    released = client.delete("/api/panic")

    assert panicked.json() == {**OFF, "panic": True}
    assert not hal.lines[PIN].active
    assert refused.status_code == 409
    assert refused.json() == {"code": "panic.active", "params": {}}
    assert released.json() == OFF


def test_websocket_sends_the_current_state_then_every_change(client: TestClient) -> None:
    with client.websocket_connect("/api/ws") as websocket:
        first = websocket.receive_json()
        client.put(f"/api/outputs/{LED}", json={"action": "on"})
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
        assert client.get("/api/status").json()["inputs"] == [
            {"id": BUTTON, "name": BUTTON, "active": False, "lostEvents": 0}
        ]


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

    assert pressed["inputs"] == [{"id": BUTTON, "name": BUTTON, "active": True, "lostEvents": 0}]
    assert released["inputs"] == [{"id": BUTTON, "name": BUTTON, "active": False, "lostEvents": 0}]


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

    response = client.put(f"/api/outputs/{LED}", json={"action": "on"})

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
        client.put(f"/api/outputs/{LED}", json={"action": "on"})
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
    return parse_config(["--no-pairing", "--pin", str(PIN), "--data-dir", str(tmp_path)], {})


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


def test_a_claim_that_fails_leaves_nothing_declared(tmp_path: Path) -> None:
    """Nothing was claimed, so there is nothing for primum-safe to make safe: a declaration
    left behind would name a pin the board may not even have."""
    # The configuration refuses such a pin by now; a claim may still fail on its own (a line
    # another program holds), and this is what it must leave behind.
    config = replace(_real(tmp_path), elements=(ElementConfig("led", "digital_output", 99, False),))
    hal = SimulatedHal(BOARD)

    with pytest.raises(PrimumError) as raised, TestClient(create_app(config, lambda: hal, {})):
        pass

    assert raised.value.code == "hal.pin_invalid"
    assert declared.read(tmp_path) is None


def test_a_start_that_fails_before_declaring_leaves_what_was_declared(tmp_path: Path) -> None:
    """An element its driver refuses fails before anything is declared: what an earlier
    service left declared is not this one's to forget."""
    earlier = Declaration("rpi4b", (OutputSpec(pin=27, active_low=False),))
    declared.write(tmp_path, earlier)
    argv = ["--no-pairing", "--pin", str(PIN), "--input-pin", "22", "--input-pull", "up"]
    config = parse_config([*argv, "--input-debounce-ms", "99999", "--data-dir", str(tmp_path)], {})
    hal = SimulatedHal(BOARD)

    with pytest.raises(PrimumError) as raised, TestClient(create_app(config, lambda: hal, {})):
        pass

    assert raised.value.code == "element.value_out_of_range"
    assert declared.read(tmp_path) == earlier


def test_a_stop_that_leaves_an_output_unsafe_keeps_it_declared(
    hal: SimulatedHal, tmp_path: Path
) -> None:
    app = create_app(_real(tmp_path), open_hal=lambda: hal, env={})

    with pytest.raises(PrimumError), TestClient(app):
        hal.lines[PIN].stick(True)

    assert declared.read(tmp_path) is not None
    assert not app.state.stopped_safely


def test_a_simulated_service_declares_nothing(hal: SimulatedHal, tmp_path: Path) -> None:
    config = parse_config(
        ["--simulate", "--no-pairing", "--pin", str(PIN), "--data-dir", str(tmp_path)], {}
    )

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


# --- a PWM output: its level, and the actions of its driver ---------------------------------

DIMMER_PIN = 18
LEVEL = ["on", "off", "set", "fade"]
WITH_DIMMER = parse_config(
    ["--simulate", "--no-pairing", "--pin", str(PIN), "--pwm-pin", str(DIMMER_PIN)], {}
)


@pytest.fixture
def dimmer_client(hal: SimulatedHal) -> Iterator[TestClient]:
    with TestClient(create_app(WITH_DIMMER, open_hal=lambda: hal)) as client:
        yield client


def _dimmer(response_json: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    return response_json["outputs"][1]


def test_a_pwm_output_is_reported_with_its_level_and_what_it_can_be_asked(
    dimmer_client: TestClient,
) -> None:
    assert _dimmer(dimmer_client.get("/api/status").json()) == {
        "id": DIMMER,
        "name": DIMMER,
        "on": False,
        "level": 0,
        "actions": LEVEL,
        "remainingMs": None,
        "restFailed": False,
        "controlledBy": None,
    }


def test_setting_a_level_drives_the_channel_and_returns_the_new_state(
    dimmer_client: TestClient, hal: SimulatedHal
) -> None:
    body = {"action": "set", "arguments": {"level": 40}}

    response = dimmer_client.put(f"/api/outputs/{DIMMER}", json=body)

    assert response.status_code == 200
    assert _dimmer(response.json()) == {
        "id": DIMMER,
        "name": DIMMER,
        "on": True,
        "level": 40,
        "actions": LEVEL,
        "remainingMs": None,
        "restFailed": False,
        "controlledBy": "manual",
    }
    assert hal.pwm_lines[DIMMER_PIN].duty == 0.4


def test_a_level_with_decimals_is_a_level(dimmer_client: TestClient, hal: SimulatedHal) -> None:
    body = {"action": "set", "arguments": {"level": 12.5}}

    assert dimmer_client.put(f"/api/outputs/{DIMMER}", json=body).status_code == 200
    assert hal.pwm_lines[DIMMER_PIN].duty == 0.125


@pytest.mark.parametrize(
    ("body", "code", "params"),
    [
        (
            {"action": "set", "arguments": {"level": 101}},
            "element.value_out_of_range",
            {"name": "level", "min": 0, "max": 100},
        ),
        ({"action": "set"}, "element.value_missing", {"name": "level"}),
        (
            {"action": "set", "arguments": {"level": "high"}},
            "element.value_invalid",
            {"name": "level"},
        ),
        (
            {"action": "set", "arguments": {"level": 5, "speed": 2}},
            "element.value_unknown",
            {"name": "speed"},
        ),
        (
            {"action": "blink"},
            "element.action_unknown",
            {"action": "blink", "available": LEVEL},
        ),
    ],
)
def test_what_an_output_cannot_do_or_take_is_the_caller_s_mistake(
    dimmer_client: TestClient,
    hal: SimulatedHal,
    body: dict[str, object],
    code: str,
    params: dict[str, object],
) -> None:
    response = dimmer_client.put(f"/api/outputs/{DIMMER}", json=body)

    assert response.status_code == 422
    assert response.json() == {"code": code, "params": {"element": DIMMER, **params}}
    assert hal.pwm_lines[DIMMER_PIN].history == ()


def test_a_digital_output_refuses_a_level(client: TestClient, hal: SimulatedHal) -> None:
    response = client.put(f"/api/outputs/{LED}", json={"action": "set", "arguments": {"level": 5}})

    assert response.status_code == 422
    assert response.json()["code"] == "element.action_unknown"
    assert not hal.lines[PIN].active


def test_panic_takes_the_pwm_output_to_0_and_refuses_levels(
    dimmer_client: TestClient, hal: SimulatedHal
) -> None:
    dimmer_client.put(f"/api/outputs/{DIMMER}", json={"action": "on"})

    panicked = dimmer_client.post("/api/panic")
    refused = dimmer_client.put(f"/api/outputs/{DIMMER}", json={"action": "on"})

    assert _dimmer(panicked.json())["level"] == 0
    assert hal.pwm_lines[DIMMER_PIN].duty == 0.0
    assert refused.status_code == 409


def test_a_real_service_declares_its_pwm_output_with_its_frequency(
    hal: SimulatedHal, tmp_path: Path
) -> None:
    argv = [
        "--no-pairing",
        "--pin",
        str(PIN),
        "--pwm-pin",
        str(DIMMER_PIN),
        "--pwm-frequency-hz",
        "25000",
    ]
    config = parse_config([*argv, "--data-dir", str(tmp_path)], {})

    with TestClient(create_app(config, open_hal=lambda: hal, env={})):
        running = declared.read(tmp_path)

    assert running == Declaration(
        "rpi4b",
        (OutputSpec(pin=PIN, active_low=False),),
        (PwmSpec(pin=DIMMER_PIN, frequency_hz=25_000),),
    )


# --- test mode: a command that expires on its own -------------------------------------------


def test_a_command_with_a_duration_is_a_test_and_says_how_long_is_left(
    client: TestClient, hal: SimulatedHal
) -> None:
    response = client.put(f"/api/outputs/{LED}", json={"action": "on", "durationMs": 10_000})

    (led,) = response.json()["outputs"]
    assert response.status_code == 200
    assert hal.lines[PIN].active
    assert 9_000 < led["remainingMs"] <= 10_000


def test_a_command_without_a_duration_ends_a_test_and_stays(client: TestClient) -> None:
    client.put(f"/api/outputs/{LED}", json={"action": "on", "durationMs": 10_000})

    response = client.put(f"/api/outputs/{LED}", json={"action": "on"})

    assert response.json() == ON


@pytest.mark.parametrize("duration_ms", [0, 999, 300_001])
def test_a_duration_outside_what_a_test_may_last_is_the_caller_s_mistake(
    client: TestClient, hal: SimulatedHal, duration_ms: int
) -> None:
    body = {"action": "on", "durationMs": duration_ms}

    response = client.put(f"/api/outputs/{LED}", json=body)

    assert response.status_code == 422
    assert response.json() == {
        "code": "test.duration_out_of_range",
        "params": {"duration_ms": duration_ms, "min_ms": 1_000, "max_ms": 300_000},
    }
    assert not hal.lines[PIN].active


def test_a_duration_that_is_not_a_whole_number_is_an_invalid_request(client: TestClient) -> None:
    response = client.put(f"/api/outputs/{LED}", json={"action": "on", "durationMs": "10 s"})

    assert response.status_code == 422
    assert response.json()["code"] == "request.invalid"


def test_a_test_expires_in_the_running_service_by_the_timer_of_its_own_loop(
    client: TestClient, hal: SimulatedHal
) -> None:
    """The one test that waits, for a second: nothing else would notice if the service
    stopped arming the timer. The WebSocket tells when the test is over; nothing polls. The
    wait is bounded, so that a timer that is never armed fails the test instead of hanging
    it."""
    waiting = ThreadPoolExecutor(max_workers=1)
    try:
        with client.websocket_connect("/api/ws") as websocket:
            websocket.receive_json()
            client.put(f"/api/outputs/{LED}", json={"action": "on", "durationMs": 1_000})
            started = websocket.receive_json()
            expired = waiting.submit(websocket.receive_json).result(timeout=EXPIRY_WAIT_S)
    finally:
        waiting.shutdown(wait=False)

    assert started["outputs"][0]["on"]
    assert expired == OFF
    assert not hal.lines[PIN].active
