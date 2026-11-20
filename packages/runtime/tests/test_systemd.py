"""Telling systemd the service is ready and alive."""

import asyncio
import socket
from pathlib import Path

import pytest

from primum_runtime import systemd


def _listener(path: Path) -> socket.socket:
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    listener.bind(str(path))
    listener.setblocking(False)
    return listener


def test_a_state_reaches_the_socket_systemd_gave(tmp_path: Path) -> None:
    address = tmp_path / "notify"
    with _listener(address) as listener:
        notify = systemd.notifier({"NOTIFY_SOCKET": str(address)})

        assert notify(systemd.READY)
        assert listener.recv(64) == b"READY=1"


def test_outside_systemd_nothing_is_sent_and_nothing_fails() -> None:
    assert not systemd.notifier({})(systemd.READY)


def test_a_socket_that_is_gone_is_not_a_reason_to_die(tmp_path: Path) -> None:
    notify = systemd.notifier({"NOTIFY_SOCKET": str(tmp_path / "gone")})

    assert not notify(systemd.WATCHDOG)


@pytest.mark.parametrize(
    ("env", "interval"),
    [
        ({"WATCHDOG_USEC": "10000000"}, 5.0),  # heard from twice in the ten seconds allowed
        ({"WATCHDOG_USEC": "0"}, None),
        ({"WATCHDOG_USEC": "soon"}, None),
        ({}, None),
    ],
)
def test_the_beats_come_twice_in_the_time_systemd_allows(
    env: dict[str, str], interval: float | None
) -> None:
    assert systemd.watchdog_interval_s(env) == interval


def test_the_watchdog_is_fed_at_each_interval_until_cancelled() -> None:
    sent: list[str] = []
    slept: list[float] = []

    def notify(state: str) -> bool:
        sent.append(state)
        return True

    async def sleep(seconds: float) -> None:
        slept.append(seconds)
        if len(slept) == 3:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(systemd.feed_watchdog(notify, 5.0, sleep))

    assert sent == [systemd.WATCHDOG] * 3
    assert slept == [5.0] * 3
