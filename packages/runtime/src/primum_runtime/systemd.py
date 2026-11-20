"""Telling systemd how the service is doing (``sd_notify``), without a library.

Under a unit of ``Type=notify``, systemd gives the service a socket (``NOTIFY_SOCKET``) and,
with ``WatchdogSec=``, the time within which it must hear from it (``WATCHDOG_USEC``). The
service says ``READY=1`` once it is up and ``WATCHDOG=1`` while it is alive; if it goes
silent, systemd kills it and what follows a stop follows (``primum-safe``, a restart).

Outside systemd (a laptop, the tests) there is no socket: nothing is sent, and nothing fails.
"""

import socket
from collections.abc import Awaitable, Callable, Mapping

READY = "READY=1"
STOPPING = "STOPPING=1"
WATCHDOG = "WATCHDOG=1"
USEC_PER_S = 1_000_000
# Heard from twice in each period systemd allows, so that one late beat is not a death.
BEATS_PER_TIMEOUT = 2

type Notify = Callable[[str], bool]


def notifier(env: Mapping[str, str]) -> Notify:
    """What sends a state to systemd: whether it was sent. Without ``NOTIFY_SOCKET`` it sends
    nothing. A failure to send is not raised: the service must not die of telling it lives."""
    address = env.get("NOTIFY_SOCKET", "")
    if not address:
        return lambda _state: False
    # A leading "@" names a socket in the abstract namespace, which starts with a NUL.
    target = "\0" + address[1:] if address.startswith("@") else address

    def notify(state: str) -> bool:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sender:
                sender.sendto(state.encode(), target)
        except OSError:
            return False
        return True

    return notify


def watchdog_interval_s(env: Mapping[str, str]) -> float | None:
    """How often to tell systemd the service is alive; ``None`` when it does not ask."""
    timeout = env.get("WATCHDOG_USEC", "")
    if not timeout.isdecimal() or int(timeout) == 0:
        return None
    return int(timeout) / USEC_PER_S / BEATS_PER_TIMEOUT


async def feed_watchdog(
    notify: Notify, interval_s: float, sleep: Callable[[float], Awaitable[None]]
) -> None:
    """Tell systemd the service is alive, every ``interval_s``, until cancelled. It runs on
    the event loop the API runs on: a loop that is stuck stops the beats."""
    while True:
        notify(WATCHDOG)
        await sleep(interval_s)
