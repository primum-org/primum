"""Waking the controller when it next has something to do: a test is due to expire, a command
of a running sequence starts or ends, an output is due to be tried again, the minute turns
and a schedule may be due.

The controller keeps the deadlines; the event loop keeps the time. After every change of
state this arms one timer for the next deadline, replacing the one before: a timer that
fires calls ``Controller.expire``, which changes the state, which arms the next. No thread
and no polling, as for the inputs: between two changes of a sequence nothing runs.
"""

import logging
from collections.abc import Callable
from typing import Protocol

from primum_runtime.control import Controller, State

log = logging.getLogger(__name__)

# How long until the controller is woken again after waking it failed.
RETRY_S = 1.0


class Timer(Protocol):
    def cancel(self) -> None: ...


type CallLater = Callable[[float, Callable[[], None]], Timer]  # the event loop's


class ExpiryTimer:
    """Arms the event loop for the controller's next expiry. ``close`` it on shutdown."""

    def __init__(self, controller: Controller, call_later: CallLater) -> None:
        self._controller = controller
        self._call_later = call_later
        self._timer: Timer | None = None
        self._unsubscribe = controller.subscribe(self._arm)
        # Armed from the start, not from the first change of state: a package with schedules
        # has something to do before anyone asks anything.
        self._arm(controller.state())

    def close(self) -> None:
        self._unsubscribe()
        self._cancel()

    def _arm(self, _state: State) -> None:
        self._cancel()
        delay_s = self._controller.next_expiry_s()
        if delay_s is not None:
            self._timer = self._call_later(delay_s, self._fire)

    def _fire(self) -> None:
        self._timer = None
        try:
            self._controller.expire()
        except Exception:
            # ``expire`` is not meant to raise. If it does, the timer must still be armed
            # again, or tests would never expire and sequences would stop where they were;
            # and not at once, or a failure that stays would spin the event loop.
            log.exception("waking the controller failed; trying again in %g s", RETRY_S)
            self._timer = self._call_later(RETRY_S, self._fire)
            return
        # ``expire`` told the listeners only if something expired: a timer that fired a
        # moment early, by the loop's clock, must be armed again for what is left.
        if self._timer is None:
            self._arm(self._controller.state())

    def _cancel(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
