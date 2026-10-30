"""The HTTP API and the WebSocket, through FastAPI's test client and the simulated HAL."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from primum_runtime.api import create_app
from primum_runtime.config import LED, RuntimeConfig
from primum_runtime.hal import OutputSpec, SimulatedHal

PIN = 17
CONFIG = RuntimeConfig(
    simulate=True, chip=None, outputs={LED: OutputSpec(pin=PIN)}, host="127.0.0.1", port=8080
)
OFF = {"outputs": [{"name": LED, "on": False}], "panic": False}
ON = {"outputs": [{"name": LED, "on": True}], "panic": False}


@pytest.fixture
def hal() -> SimulatedHal:
    return SimulatedHal()


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
