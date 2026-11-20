"""The service as a real process: stopping it with `SIGTERM`, as systemd does, applies the
safe state. Measured on a Pi before this existed: `SIGTERM` left the line on (decision 0010).

The process uses the simulated HAL and reports the final state of its outputs in its log.
"""

import json
import os
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
READ_BYTES = 65536


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def _log_until(process: subprocess.Popen[bytes], marker: str) -> str:
    """Read the process's log until it contains ``marker``; fail after ``TIMEOUT_S``.

    Read from the descriptor itself, with no buffer in between: a buffered reader may take two
    lines at once and keep the second, and then waiting on the descriptor never ends although
    the line with the marker has arrived.
    """
    assert process.stderr is not None
    descriptor = process.stderr.fileno()
    deadline = time.monotonic() + TIMEOUT_S
    log = ""
    with selectors.DefaultSelector() as selector:
        selector.register(descriptor, selectors.EVENT_READ)
        while marker not in log:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                pytest.fail(f"no {marker!r} in the log after {TIMEOUT_S} s: {log}")
            chunk = os.read(descriptor, READ_BYTES)
            if not chunk:
                pytest.fail(f"the process ended before {marker!r}: {log}")
            log += chunk.decode()
    return log


@pytest.fixture
def service() -> Iterator[tuple[subprocess.Popen[bytes], int]]:
    port = _free_port()
    command = [sys.executable, "-m", "primum_runtime", "--simulate", "--pin", "17"]
    process = subprocess.Popen(  # noqa: S603 (fixed command, this interpreter)
        [*command, "--port", str(port)], stderr=subprocess.PIPE, bufsize=0
    )
    try:
        _log_until(process, STARTED)
        yield process, port
    finally:
        process.kill()
        process.wait(TIMEOUT_S)


def _turn_led_on(port: int) -> object:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/outputs/led",
        data=json.dumps({"action": "on"}).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 (loopback)
        return json.load(response)


def test_sigterm_stops_the_service_with_every_output_in_its_safe_state(
    service: tuple[subprocess.Popen[bytes], int],
) -> None:
    process, port = service
    assert _turn_led_on(port) == {
        "outputs": [
            {
                "name": "led",
                "on": True,
                "level": 100,
                "actions": ["on", "off"],
                "remainingMs": None,
                "restFailed": False,
            }
        ],
        "inputs": [],
        "panic": False,
    }

    process.send_signal(signal.SIGTERM)
    _, rest = process.communicate(timeout=TIMEOUT_S)
    log = rest.decode()

    # uvicorn shuts down, then re-raises the signal: the process ends by SIGTERM, as systemd
    # expects. The log line is written only after the HAL closed without errors.
    assert process.returncode == -signal.SIGTERM, log
    assert "stopped outputs=led:off" in log
