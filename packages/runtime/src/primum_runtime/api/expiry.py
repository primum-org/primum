"""Waking the controller when a test is due to expire.

The controller keeps the deadlines; the event loop keeps the time. After every change of
state this arms one timer for the next deadline, replacing the one before: a timer that
fires calls ``Controller.expire``, which changes the state, which arms the next. No thread
and no polling, as for the inputs.
"""

from collections.abc import Callable
from typing import Protocol

from primum_runtime.control import Controller, State


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
        self._controller.expire()
        # ``expire`` told the listeners only if something expired: a timer that fired a
        # moment early, by the loop's clock, must be armed again for what is left.
        if self._timer is None:
            self._arm(self._controller.state())

    def _cancel(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
