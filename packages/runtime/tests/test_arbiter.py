"""The controller as the arbiter of its outputs: panic, then a person, then the sequences of
the package (decision 0006), on the simulated HAL with a clock moved by hand."""

import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from primum_runtime.board import load_board, option_limits
from primum_runtime.control import RETRY_REST_S, Controller
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.hal import SimulatedHal
from primum_runtime.package import check_against_board
from show_service import (
    BLINK,
    DIM,
    DOWN,
    GLOW,
    LAMP,
    LED,
    LED_PIN,
    MANIFESTS,
    ON,
    OVER,
    PROFILE,
    PULSE,
    RISE,
    SLOW_PULSE,
    UNKNOWN,
    WAIT_S,
    Service,
    package,
    running,
)


@pytest.fixture
def service() -> Service:
    return Service()


def test_a_sequence_commands_its_element_in_its_time_and_gives_it_back(service: Service) -> None:
    service.controller.start_sequence(BLINK)
    before = (service.led, service.by(), service.running())

    service.after(1)
    during = (service.led, service.by())
    service.after(1)

    assert before == (False, None, ["Blink"])  # its clip starts a second in
    assert during == (True, "sequence")
    assert (service.led, service.by(), service.running()) == (False, None, [])


def test_the_controller_says_when_it_next_has_something_to_do(service: Service) -> None:
    assert service.controller.next_expiry_s() is None

    service.controller.start_sequence(BLINK)
    first = service.controller.next_expiry_s()
    service.after(1)
    second = service.controller.next_expiry_s()
    service.after(1)

    assert (first, second) == (1.0, 1.0)  # the clip starts, then it ends with its sequence
    assert service.controller.next_expiry_s() is None


def test_waking_early_changes_nothing_and_tells_nobody(service: Service) -> None:
    service.controller.start_sequence(BLINK)
    told = len(service.states)

    service.after(0.5)

    assert not service.led
    assert len(service.states) == told
    assert service.controller.next_expiry_s() == 0.5


def test_a_sequence_that_holds_stays_until_it_is_stopped(service: Service) -> None:
    service.controller.start_sequence(ON)
    service.after(3600)
    held = (service.led, service.running(), service.controller.next_expiry_s())

    service.controller.stop_sequence(ON)

    assert held == (True, ["On"], None)
    assert (service.led, service.running()) == (False, [])


def test_a_higher_priority_commands_while_it_runs_and_then_gives_the_element_back(
    service: Service,
) -> None:
    service.controller.start_sequence(ON)
    service.controller.start_sequence(OVER)
    over = (service.led, service.running())

    service.after(2)

    assert over == (False, ["On", "Over"])
    assert (service.led, service.running()) == (True, ["On"])


def test_an_output_is_written_only_when_what_it_should_be_changes(service: Service) -> None:
    service.controller.start_sequence(ON)
    service.controller.start_sequence(BLINK)  # asks for the same from 1 s to 2 s
    service.after(1)
    service.after(1)
    service.controller.stop_sequence(BLINK)

    assert service.hal.lines[LED_PIN].history == (True,)


def test_a_variable_is_read_at_its_initial_value(service: Service) -> None:
    service.controller.start_sequence(DIM)

    assert service.lamp == 0.6
    assert service.by(LAMP) == "sequence"


def test_manual_control_is_over_the_sequences_until_it_is_released(service: Service) -> None:
    service.controller.start_sequence(ON)

    service.controller.command(LED, "off")
    held = (service.led, service.by())
    service.after(3600)
    still = (service.led, service.by())
    service.controller.release(LED)

    assert held == still == (False, "manual")
    assert (service.led, service.by()) == (True, "sequence")


def test_a_sequence_started_under_manual_control_waits_for_its_turn(service: Service) -> None:
    service.controller.command(LED, "off")

    service.controller.start_sequence(ON)
    under = (service.led, service.by(), service.running())
    service.controller.release(LED)

    assert under == (False, "manual", ["On"])
    assert service.led


def test_a_test_that_expires_gives_the_output_back_to_the_sequences(service: Service) -> None:
    service.controller.start_sequence(ON)

    service.controller.command(LED, "off", duration_ms=2000)
    testing = (service.led, service.by())
    service.after(2)

    assert testing == (False, "test")
    assert (service.led, service.by()) == (True, "sequence")


def test_a_test_that_expires_with_nothing_under_it_goes_to_rest(service: Service) -> None:
    service.controller.command(LED, "on", duration_ms=2000)

    service.after(2)

    assert (service.led, service.by()) == (False, None)


def test_releasing_an_output_nobody_holds_changes_nothing_and_tells_nobody(
    service: Service,
) -> None:
    service.controller.start_sequence(ON)
    told = len(service.states)

    service.controller.release(LED)

    assert service.led
    assert len(service.states) == told


def test_releasing_ends_a_test_too(service: Service) -> None:
    service.controller.command(LED, "on", duration_ms=60_000)

    service.controller.release(LED)

    assert (service.led, service.by(), service.controller.next_expiry_s()) == (False, None, None)


def test_panic_stops_every_sequence_and_ends_manual_control(service: Service) -> None:
    service.controller.start_sequence(ON)
    service.controller.start_sequence(DIM)
    service.controller.command(LAMP, "set", {"level": 80})

    service.controller.panic()
    panicked = (service.led, service.lamp, service.running(), service.by(), service.by(LAMP))
    with pytest.raises(PrimumError) as refused:
        service.controller.start_sequence(ON)
    service.controller.release_panic()
    service.after(60)

    assert panicked == (False, 0.0, [], None, None)
    assert refused.value.code is ErrorCode.PANIC_ACTIVE
    assert (service.led, service.lamp, service.running()) == (False, 0.0, [])


def test_the_state_lists_the_sequences_of_the_package_and_which_are_running(
    service: Service,
) -> None:
    service.controller.start_sequence(ON)

    sequences = service.controller.state().sequences

    assert [(sequence.id, sequence.name, sequence.running) for sequence in sequences] == [
        (BLINK, "Blink", False),
        (DIM, "Dim", False),
        (DOWN, "Down", False),
        (GLOW, "Glow", False),
        (ON, "On", True),
        (OVER, "Over", False),
        (PULSE, "Pulse", False),
        (RISE, "Rise", False),
        (SLOW_PULSE, "Slow pulse", False),
    ]


def test_listeners_are_told_when_a_sequence_ends_though_no_output_changes(
    service: Service,
) -> None:
    service.controller.command(LED, "off")  # held by a person: the sequence moves nothing
    service.controller.start_sequence(BLINK)
    told = len(service.states)

    service.after(2)

    assert len(service.states) == told + 1
    assert service.states[-1].sequences[0].running is False


@pytest.mark.parametrize("sequence", [UNKNOWN, "blink", ""])
def test_a_sequence_the_package_does_not_have_is_refused(service: Service, sequence: str) -> None:
    for ask in (service.controller.start_sequence, service.controller.stop_sequence):
        with pytest.raises(PrimumError) as refused:
            ask(sequence)
        assert (refused.value.code, dict(refused.value.params)) == (
            ErrorCode.SEQUENCE_UNKNOWN,
            {"id": sequence},
        )


def test_an_output_that_does_not_follow_a_sequence_does_not_stop_the_others(
    service: Service, caplog: pytest.LogCaptureFixture
) -> None:
    """The LED cannot be written: the lamp still follows its sequence, the LED says it is
    not where it should be, and it is tried again until it is."""
    caplog.set_level(logging.INFO)
    service.hal.lines[LED_PIN].fail_writes(OSError(5, "I/O error"))

    service.controller.start_sequence(ON)
    service.controller.start_sequence(DIM)
    failed = {output.id: output.rest_failed for output in service.controller.state().outputs}
    waiting = service.controller.next_expiry_s()
    service.hal.lines[LED_PIN].fail_writes(None)
    service.after(RETRY_REST_S)

    assert failed == {LED: True, LAMP: False}
    assert service.lamp == 0.0  # Dim ended a second in, well before the retry
    assert waiting == 1.0  # the end of Dim comes before the retry of the LED
    assert service.led
    assert not service.controller.state().outputs[0].rest_failed
    assert caplog.text.count("LED could not be taken where it should be") == 1
    assert "LED is where it should be after all" in caplog.text


def test_without_a_package_there_are_no_sequences(service: Service) -> None:
    hal = SimulatedHal(load_board("rpi4b"))
    elements = (replace(check_against_board(package(), MANIFESTS)[0], id=None),)
    controller = Controller(hal, elements, MANIFESTS, option_limits(PROFILE))

    assert controller.state().sequences == ()
    with pytest.raises(PrimumError) as refused:
        controller.start_sequence(ON)
    assert refused.value.code is ErrorCode.SEQUENCE_UNKNOWN


# --- over the API --------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, SimulatedHal]]:
    with running(tmp_path) as service:
        yield service


def test_sequences_are_started_and_stopped_over_the_api(
    client: tuple[TestClient, SimulatedHal],
) -> None:
    api, hal = client

    started = api.post(f"/api/sequences/{ON}/start")
    running = [s["name"] for s in started.json()["sequences"] if s["running"]]
    led = started.json()["outputs"][0]
    stopped = api.post(f"/api/sequences/{ON}/stop")

    assert (started.status_code, running) == (200, ["On"])
    assert (led["on"], led["controlledBy"]) == (True, "sequence")
    assert stopped.json()["outputs"][0]["on"] is False
    assert not hal.lines[LED_PIN].active


def test_an_output_is_released_over_the_api(client: tuple[TestClient, SimulatedHal]) -> None:
    api, hal = client
    api.post(f"/api/sequences/{ON}/start")
    api.put(f"/api/outputs/{LED}", json={"action": "off"})

    released = api.delete(f"/api/outputs/{LED}")

    assert released.status_code == 200
    assert released.json()["outputs"][0]["controlledBy"] == "sequence"
    assert hal.lines[LED_PIN].active


def test_what_is_not_there_is_a_404_and_panic_a_409(
    client: tuple[TestClient, SimulatedHal],
) -> None:
    api, _ = client

    unknown = api.post(f"/api/sequences/{UNKNOWN}/start")
    nothing = api.delete("/api/outputs/fan")
    api.post("/api/panic")
    refused = api.post(f"/api/sequences/{ON}/start")

    assert (unknown.status_code, unknown.json()) == (
        404,
        {"code": "sequence.unknown", "params": {"id": UNKNOWN}},
    )
    assert (nothing.status_code, nothing.json()["code"]) == (404, "output.unknown")
    assert (refused.status_code, refused.json()["code"]) == (409, "panic.active")


def test_a_sequence_runs_in_the_running_service_by_the_timer_of_its_own_loop(
    client: tuple[TestClient, SimulatedHal],
) -> None:
    """The one test of sequences that waits, for two seconds: nothing else would notice if
    the service stopped arming its timer for them. The WebSocket tells each change; nothing
    polls, and the wait is bounded."""
    api, hal = client
    waiting = ThreadPoolExecutor(max_workers=1)
    try:
        with api.websocket_connect("/api/ws") as websocket:
            websocket.receive_json()
            api.post(f"/api/sequences/{BLINK}/start")
            websocket.receive_json()  # started
            lit = waiting.submit(websocket.receive_json).result(timeout=WAIT_S)
            ended = waiting.submit(websocket.receive_json).result(timeout=WAIT_S)
    finally:
        waiting.shutdown(wait=False)

    assert lit["outputs"][0]["on"] is True
    assert ended["outputs"][0]["on"] is False
    assert [s["name"] for s in ended["sequences"] if s["running"]] == []
    assert hal.lines[LED_PIN].history == (True, False)
