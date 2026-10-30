"""The service as a real process: stopping it with `SIGTERM`, as systemd does, applies the
safe state. Measured on a Pi before this existed: `SIGTERM` left the line on (decision 0010).

The process uses the simulated HAL and reports the final state of its outputs in its log.
"""

import json
import selectors
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals and pipes")

TIMEOUT_S = 10
STARTED = "Application startup complete"


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def _lines_until(process: subprocess.Popen[str], marker: str) -> list[str]:
    """Read the process's log until a line contains ``marker``; fail after ``TIMEOUT_S``."""
    assert process.stderr is not None
    deadline = time.monotonic() + TIMEOUT_S
    lines: list[str] = []
    with selectors.DefaultSelector() as selector:
        selector.register(process.stderr, selectors.EVENT_READ)
        while not lines or marker not in lines[-1]:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                pytest.fail(f"no {marker!r} in the log after {TIMEOUT_S} s: {lines}")
            line = process.stderr.readline()
            if not line:
                pytest.fail(f"the process ended before {marker!r}: {lines}")
            lines.append(line)
    return lines


@pytest.fixture
def service() -> Iterator[tuple[subprocess.Popen[str], int]]:
    port = _free_port()
    command = [sys.executable, "-m", "primum_runtime", "--simulate", "--pin", "17"]
    process = subprocess.Popen(  # noqa: S603 (fixed command, this interpreter)
        [*command, "--port", str(port)], stderr=subprocess.PIPE, text=True
    )
    try:
        _lines_until(process, STARTED)
        yield process, port
    finally:
        process.kill()
        process.wait(TIMEOUT_S)


def _turn_led_on(port: int) -> object:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/outputs/led",
        data=json.dumps({"on": True}).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 (loopback)
        return json.load(response)


def test_sigterm_stops_the_service_with_every_output_in_its_safe_state(
    service: tuple[subprocess.Popen[str], int],
) -> None:
    process, port = service
    assert _turn_led_on(port) == {"outputs": [{"name": "led", "on": True}], "panic": False}

    process.send_signal(signal.SIGTERM)
    _, log = process.communicate(timeout=TIMEOUT_S)

    # uvicorn shuts down, then re-raises the signal: the process ends by SIGTERM, as systemd
    # expects. The log line is written only after the HAL closed without errors.
    assert process.returncode == -signal.SIGTERM, log
    assert "stopped outputs=led:off" in log
