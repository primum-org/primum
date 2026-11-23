"""The trace: what the board did, and why, as it happened (decision 0032).

An entry is a decision, not a measurement: something happened, an automation acted or did
not, a sequence started or ended, a person commanded an output, panic. The levels of the
outputs are the state's to tell, and the steps of a fade are nobody's.

Each entry has a ``kind`` (a stable code, as an error has) and ``params``, never text; a
number that only grows, so that whoever follows the trace asks for what came after the last
one it has; and, when something led to it, the number of that entry (``cause``): the
automation that started a sequence, the event that concerned the automation.

The trace is kept in memory, the last ``SIZE`` entries: it tells what has just happened and
does not wear a card. It starts empty when the service does, with a new id (``run``) and its
numbers from 1 again; the journal has the rest.
"""

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import uuid4

from primum_runtime.errors import ErrorParam

SIZE = 1000

type Listener = Callable[[], None]


class Kind(StrEnum):
    """Every kind of entry the trace can have. Each one has its row in
    ``docs/specs/trace.md`` (a test checks it). Kinds are a public contract, as error codes
    are: adding one is free, renaming one breaks whoever reads the trace."""

    SERVICE_STARTED = "service.started"
    PACKAGE_STORED = "package.stored"
    PACKAGE_ACTIVATED = "package.activated"
    PACKAGE_REFUSED = "package.refused"
    EVENT_HAPPENED = "event.happened"
    EVENT_IGNORED = "event.ignored"
    EVENT_FAILED = "event.failed"
    AUTOMATION_ACTED = "automation.acted"
    AUTOMATION_DID_NOT_ACT = "automation.did_not_act"
    AUTOMATION_FAILED = "automation.failed"
    SEQUENCE_STARTED = "sequence.started"
    SEQUENCE_STOPPED = "sequence.stopped"
    SEQUENCE_ENDED = "sequence.ended"
    VARIABLE_CHANGED = "variable.changed"
    VARIABLE_KEPT_VALUE_DROPPED = "variable.kept_value_dropped"
    OUTPUT_COMMANDED = "output.commanded"
    OUTPUT_RELEASED = "output.released"
    OUTPUT_TEST_ENDED = "output.test_ended"
    OUTPUT_FAILED = "output.failed"
    OUTPUT_RECOVERED = "output.recovered"
    PANIC_ON = "panic.on"
    PANIC_RELEASED = "panic.released"
    TIME_KNOWN = "time.known"
    TIME_UNKNOWN = "time.unknown"
    VARIABLES_UNSAVED = "variables.unsaved"
    VARIABLES_SAVED = "variables.saved"


@dataclass(frozen=True)
class Entry:
    """One thing the board did. ``at_ms`` counts from when the service started, on the clock
    that never jumps; ``time`` is the time of day, when the board knows it."""

    number: int
    at_ms: int
    kind: Kind
    params: Mapping[str, ErrorParam]
    cause: int | None = None
    time: datetime | None = None


class Trace:
    """The last entries, in order. Used from one thread, the event loop's."""

    def __init__(self, size: int = SIZE) -> None:
        self._entries: deque[Entry] = deque(maxlen=size)
        self._last = 0
        # Numbers start again at 1 with every trace. Whoever follows one keeps its id, and
        # knows by it that what it has is of another: the service restarted.
        self.run = uuid4().hex
        self._listeners: list[Listener] = []

    def add(
        self,
        kind: Kind,
        params: Mapping[str, ErrorParam],
        at_ms: int,
        time: datetime | None = None,
        cause: int | None = None,
    ) -> int:
        """Note an entry; its number, to give as the ``cause`` of what follows from it.
        Listeners are told there is something new; they must not block."""
        self._last += 1
        entry = Entry(self._last, at_ms, kind, MappingProxyType(dict(params)), cause, time)
        self._entries.append(entry)
        for listener in tuple(self._listeners):
            listener()
        return self._last

    def entries(self, after: int = 0) -> tuple[Entry, ...]:
        """The entries numbered above ``after`` that are still kept, oldest first."""
        return tuple(entry for entry in self._entries if entry.number > after)

    @property
    def last(self) -> int:
        """The number of the newest entry ever noted; 0 before the first."""
        return self._last

    @property
    def first(self) -> int:
        """The number of the oldest entry still kept; one past ``last`` when none is. An
        entry below it was noted and is gone: whoever follows the trace missed it."""
        return self._entries[0].number if self._entries else self._last + 1

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Call ``listener`` after every new entry; returns an unsubscribe."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)
