"""The engine: which sequences of a package are running, and what each element is asked.

It runs the rules ``core`` decided and tests (decisions 0017 and 0023), on what a deployment
package carries: sequences as commands, each in force from an instant until another. It
touches no hardware and reads no clock: whoever owns the outputs (``control``) says what time
it is, in whole milliseconds of a monotonic clock, and asks.

- Starting a sequence stops the others of its exclusive group. Starting one that is running
  restarts it, so it counts as started last, unless it asks to ignore that.
- A sequence that does not hold stops running when its last clip ends.
- Of the commands in force on an element, those of the highest priority count, then the one
  that started last, then a command with a length over an instant one, then the sequence
  started last. With none in force, nothing is asked: the element rests.

What a sequence asks of an element depends only on the time since it started, so it is
worked out once, when the package is loaded: for each element, the instants at which what is
asked changes and what is asked from each. Asking is then a search, whatever the length of
the show: a change must never keep the event loop, and panic with it, waiting on the size of
a sequence.

Tests hold it to ``primum_core.commands.command_at`` and ``primum_core.runs`` on random
projects.
"""

import heapq
from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from uuid import UUID

from primum_core.generated.model import Command, Package, PackageSequence
from primum_runtime.errors import ErrorCode, PrimumError


@dataclass(frozen=True)
class Run:
    """A sequence that was started and has not stopped, and when it started (ms)."""

    sequence: UUID
    started_ms: int


@dataclass(frozen=True)
class Asked:
    """What an element is asked at an instant: the command, the sequence it is of, since
    when, and whether its action is over (the element stays in the state it ends in)."""

    command: Command
    sequence: UUID
    since_ms: int
    settled: bool


@dataclass(frozen=True)
class _Track:
    """What a sequence asks of one element over its own time: from ``starts[i]`` (ms since
    the sequence started) it asks ``asked[i]``, or nothing, until the next start."""

    starts: tuple[int, ...]
    asked: tuple[Command | None, ...]

    def at(self, local_ms: int) -> Command | None:
        index = bisect_right(self.starts, local_ms) - 1
        return None if index < 0 else self.asked[index]


@dataclass(frozen=True)
class _Timeline:
    """A sequence ready to be asked: what it asks of each element, and every instant of its
    own time at which something may change (a command starts, its action ends, it stops
    being in force, the sequence ends)."""

    tracks: Mapping[UUID, _Track]
    changes: tuple[int, ...]


class Engine:
    """The sequences of one package, and which of them are running."""

    def __init__(self, package: Package) -> None:
        self._sequences: Mapping[UUID, PackageSequence] = {
            sequence.id: sequence for sequence in package.sequences
        }
        self._timelines = {sequence.id: _timeline(sequence) for sequence in package.sequences}
        self._running: tuple[Run, ...] = ()  # in the order they were started

    @property
    def sequences(self) -> Iterable[PackageSequence]:
        return self._sequences.values()

    def running(self, now_ms: int) -> tuple[Run, ...]:
        """The sequences running at ``now_ms``, in the order they were started. Those that
        have ended by then are forgotten."""
        self._running = tuple(run for run in self._running if not self._ended(run, now_ms))
        return self._running

    def start(self, sequence: UUID, now_ms: int) -> None:
        """Start ``sequence``; ``sequence.unknown`` (``id``) if the package has none such."""
        starting = self._known(sequence)
        live = self.running(now_ms)
        already = any(run.sequence == sequence for run in live)
        if already and starting.when_started_again == "ignore":
            return
        group = starting.exclusive_group
        kept = tuple(
            run
            for run in live
            if run.sequence != sequence
            and (group is None or self._sequences[run.sequence].exclusive_group != group)
        )
        self._running = (*kept, Run(sequence, now_ms))

    def stop(self, sequence: UUID) -> None:
        """Stop ``sequence``; one that is not running stays so. ``sequence.unknown`` if the
        package has none such."""
        self._known(sequence)
        self._running = tuple(run for run in self._running if run.sequence != sequence)

    def stop_all(self) -> None:
        self._running = ()

    def asked(self, element: UUID, now_ms: int) -> Asked | None:
        """The command in force on ``element`` at ``now_ms``, or ``None``: it rests."""
        winner: tuple[tuple[int, int, bool, int], Asked] | None = None
        for order, run in enumerate(self.running(now_ms)):
            track = self._timelines[run.sequence].tracks.get(element)
            local = now_ms - run.started_ms
            command = None if track is None else track.at(local)
            if command is None:
                continue
            since = run.started_ms + command.at_ms
            priority = self._sequences[run.sequence].priority
            rank = (priority, since, command.duration_ms > 0, order)
            if winner is None or rank > winner[0]:
                settled = local >= command.at_ms + command.duration_ms
                winner = (rank, Asked(command, run.sequence, since, settled))
        return winner[1] if winner else None

    def next_change_ms(self, now_ms: int) -> int | None:
        """The next instant after ``now_ms`` at which what is asked may change: a command of
        a running sequence starts, ends its action or stops being in force, or a sequence
        ends. ``None`` when nothing will change until something is started or stopped."""
        instants: list[int] = []
        for run in self.running(now_ms):
            changes = self._timelines[run.sequence].changes
            index = bisect_right(changes, now_ms - run.started_ms)
            if index < len(changes):
                instants.append(run.started_ms + changes[index])
        return min(instants, default=None)

    def _known(self, sequence: UUID) -> PackageSequence:
        found = self._sequences.get(sequence)
        if found is None:
            raise PrimumError(ErrorCode.SEQUENCE_UNKNOWN, {"id": str(sequence)})
        return found

    def _ended(self, run: Run, now_ms: int) -> bool:
        sequence = self._sequences[run.sequence]
        return sequence.when_done != "hold" and now_ms - run.started_ms >= sequence.duration_ms


def _timeline(sequence: PackageSequence) -> _Timeline:
    changes: set[int] = set()
    if sequence.when_done != "hold":
        changes.add(sequence.duration_ms)
    of_element: dict[UUID, list[Command]] = {}
    for command in sequence.commands:
        of_element.setdefault(command.element, []).append(command)
        changes.add(command.at_ms)
        changes.add(command.at_ms + command.duration_ms)
        if command.until_ms is not None:
            changes.add(command.until_ms)
    tracks = {element: _track(commands) for element, commands in of_element.items()}
    return _Timeline(tracks, tuple(sorted(changes)))


def _track(commands: list[Command]) -> _Track:
    """What the commands of one element, of one sequence, ask over the time of the sequence.

    Within a sequence the priority is one, so of the commands in force the one that started
    last wins, a command with a length before an instant one. A sweep over the instants at
    which a command starts or stops being in force, with the ones in force in a heap: the
    best is on top, and one that is over is dropped when it gets there.
    """
    # A command that stops being in force no later than it starts never is.
    lasting = [c for c in commands if c.until_ms is None or c.until_ms > c.at_ms]
    by_start = sorted(enumerate(lasting), key=lambda item: item[1].at_ms)
    instants = sorted(
        {c.at_ms for c in lasting} | {c.until_ms for c in lasting if c.until_ms is not None}
    )
    in_force: list[tuple[int, int, int, Command]] = []  # best first: latest, with a length
    starts: list[int] = []
    asked: list[Command | None] = []
    following = 0
    for instant in instants:
        while following < len(by_start) and by_start[following][1].at_ms <= instant:
            index, command = by_start[following]
            best_first = (-command.at_ms, 0 if command.duration_ms > 0 else 1, index)
            heapq.heappush(in_force, (*best_first, command))
            following += 1
        while in_force and _over(in_force[0][3], instant):
            heapq.heappop(in_force)
        now_asked = in_force[0][3] if in_force else None
        if not asked or asked[-1] is not now_asked:
            starts.append(instant)
            asked.append(now_asked)
    return _Track(tuple(starts), tuple(asked))


def _over(command: Command, local_ms: int) -> bool:
    return command.until_ms is not None and command.until_ms <= local_ms
