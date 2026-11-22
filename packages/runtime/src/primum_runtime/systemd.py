"""Telling systemd how the service is doing (``sd_notify``), without a library.

Under a unit of ``Type=notify``, systemd gives the service a socket (``NOTIFY_SOCKET``) and,
with ``WatchdogSec=``, the time within which it must hear from it (``WATCHDOG_USEC``). The
service says ``READY=1`` once it is up and ``WATCHDOG=1`` while it is alive; if it goes
silent, systemd kills it and what follows a stop follows (``primum-safe``, a restart).

Outside systemd (a laptop, the tests) there is no socket: nothing is sent, and nothing fails.
"""

import socket
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

READY = "READY=1"
STOPPING = "STOPPING=1"
WATCHDOG = "WATCHDOG=1"
USEC_PER_S = 1_000_000
# Heard from twice in each period systemd allows, so that one late beat is not a death.
BEATS_PER_TIMEOUT = 2

# systemd-timesyncd touches this file each time it sets the clock from the network
# (systemd-timesyncd.service(8)): once it is there, the clock has been set since boot.
CLOCK_SYNCHRONIZED = Path("/run/systemd/timesync/synchronized")

type Notify = Callable[[str], bool]


def trusted_time(
    *, trust: bool, marker: Path = CLOCK_SYNCHRONIZED
) -> Callable[[], datetime | None]:
    """What tells the time of the system once it can be trusted, and ``None`` until then.

    A board without a clock of its own (the Pi 4 has no battery) starts at some old time,
    and is right only once it has been set from the network: when ``marker`` is there. Once
    set it stays trusted for as long as this service runs, also if the file goes (restarting
    systemd-timesyncd removes it until it next sets the clock, and the clock is no worse
    for that). ``trust`` takes the clock as right from the start: a board with its own.
    """
    known = trust

    def now() -> datetime | None:
        nonlocal known
        known = known or marker.exists()
        return datetime.now(UTC) if known else None

    return now


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
