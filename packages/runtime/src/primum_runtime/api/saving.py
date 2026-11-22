"""Keeping the values of persistent variables as they change (decision 0031).

The controller has the values; the disk is slow, and a card wears. So a change is not
written at once: after the first change a timer is armed, and when it fires the values of
that moment are written, off the event loop (a write waits for the card, and panic must
never wait behind it). However often a counter changes, the card sees one write per
``SAVE_DELAY_S``; a power cut loses at most what changed in that time. When the service
stops, what is pending is written before it goes.

A write that fails is logged, told to the controller (the state says the values are not
kept) and tried again every ``RETRY_S`` until it works.
"""

import logging
import threading
from collections.abc import Callable, Mapping
from uuid import UUID

from primum_core.values import Value
from primum_runtime.api.expiry import CallLater, Timer
from primum_runtime.control import Controller, State

log = logging.getLogger(__name__)

# How long a change waits to be written, with the ones that follow it.
SAVE_DELAY_S = 1.0
# How long until a write that failed is tried again.
RETRY_S = 30.0

type Values = Mapping[UUID, Value]
type Write = Callable[[Values], None]
# Runs a write off the event loop and calls back, on the loop, with what it raised, if
# anything.
type Submit = Callable[[Callable[[], None], Callable[[BaseException | None], None]], None]


class VariableSaver:
    """Writes the persistent values of ``controller`` when they change. ``close`` it on
    shutdown: it writes what is pending."""

    def __init__(
        self,
        controller: Controller,
        write: Write,
        call_later: CallLater,
        submit: Submit,
        kept: Values,
    ) -> None:
        """``kept`` are the values on disk now: nothing is written until one differs."""
        self._controller = controller
        self._write = write
        self._call_later = call_later
        self._submit = submit
        self._kept = dict(kept)
        self._timer: Timer | None = None
        self._writing = False
        self._failed = False
        self._closed = False
        # Each write has its turn, in the order they were asked for.
        self._order = threading.Lock()
        self._turns = 0
        self._written_turn = 0
        self._unsubscribe = controller.subscribe(self._changed)
        self._changed(controller.state())  # values restored differently than they were kept

    def close(self) -> None:
        """Stop following the controller, and write what is not kept yet: now, and here,
        since nothing comes after. A write still under way in its thread is older: it
        writes nothing if it gets to the card later, and arms nothing when it ends."""
        self._closed = True
        self._unsubscribe()
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        values = self._controller.persistent_values()
        if values == self._kept:
            return
        try:
            self._write_in_turn(self._next_turn(), values)
        except Exception:
            log.exception("the persistent variables could not be kept on stopping")

    def _next_turn(self) -> int:
        self._turns += 1
        return self._turns

    def _write_in_turn(self, turn: int, values: Values) -> None:
        """Write, unless values asked for later have been written already: writes run in
        threads, and the one handed over first is not always the first to get there."""
        with self._order:
            if turn < self._written_turn:
                return
            self._write(values)
            self._written_turn = turn

    def _changed(self, _state: State) -> None:
        if self._closed:
            return
        if self._timer is None and not self._writing and self._pending():
            self._timer = self._call_later(SAVE_DELAY_S, self._save)

    def _pending(self) -> bool:
        return self._controller.persistent_values() != self._kept

    def _save(self) -> None:
        self._timer = None
        if not self._pending():
            # Nothing left to write: a write that failed before has nothing to keep any
            # more (the value went back to what is on the board).
            self._settled()
            return
        values = self._controller.persistent_values()
        turn = self._next_turn()
        self._writing = True

        def done(error: BaseException | None) -> None:
            self._writing = False
            if self._closed:
                return
            if error is None:
                self._kept = values
                self._settled()
                self._changed(self._controller.state())  # what changed while it was written
            else:
                if not self._failed:  # said once, not at every retry: the state goes on saying it
                    log.error(
                        "the persistent variables could not be kept (trying again every %g s): %s",
                        RETRY_S,
                        error,
                    )
                self._failed = True
                # Armed before the controller is told: telling it changes the state, and a
                # change with no timer armed would arm one for a moment from now.
                self._timer = self._call_later(RETRY_S, self._save)
                self._controller.values_kept(False)

        self._submit(lambda: self._write_in_turn(turn, values), done)

    def _settled(self) -> None:
        """What is on the board is what the variables are worth: say so, if it was not."""
        if self._failed:
            log.info("the persistent variables are kept again")
        self._failed = False
        self._controller.values_kept(True)
