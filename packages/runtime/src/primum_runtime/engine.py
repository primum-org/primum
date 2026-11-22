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

Tests hold it to ``primum_core.commands.command_at`` and ``primum_core.runs`` on random
projects.
"""

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


class Engine:
    """The sequences of one package, and which of them are running."""

    def __init__(self, package: Package) -> None:
        self._sequences: Mapping[UUID, PackageSequence] = {
            sequence.id: sequence for sequence in package.sequences
        }
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
            sequence = self._sequences[run.sequence]
            local = now_ms - run.started_ms
            for command in sequence.commands:
                if command.element != element or not _in_force(command, local):
                    continue
                since = run.started_ms + command.at_ms
                rank = (sequence.priority, since, command.duration_ms > 0, order)
                if winner is None or rank > winner[0]:
                    settled = local >= command.at_ms + command.duration_ms
                    winner = (rank, Asked(command, run.sequence, since, settled))
        return winner[1] if winner else None

    def next_change_ms(self, now_ms: int) -> int | None:
        """The next instant after ``now_ms`` at which what is asked may change: a command of
        a running sequence starts or stops being in force, or a sequence ends. ``None`` when
        nothing will change until something is started or stopped."""
        instants: list[int] = []
        for run in self.running(now_ms):
            sequence = self._sequences[run.sequence]
            if sequence.when_done != "hold":
                instants.append(run.started_ms + sequence.duration_ms)
            for command in sequence.commands:
                instants.append(run.started_ms + command.at_ms)
                if command.until_ms is not None:
                    instants.append(run.started_ms + command.until_ms)
        return min((instant for instant in instants if instant > now_ms), default=None)

    def _known(self, sequence: UUID) -> PackageSequence:
        found = self._sequences.get(sequence)
        if found is None:
            raise PrimumError(ErrorCode.SEQUENCE_UNKNOWN, {"id": str(sequence)})
        return found

    def _ended(self, run: Run, now_ms: int) -> bool:
        sequence = self._sequences[run.sequence]
        return sequence.when_done != "hold" and now_ms - run.started_ms >= sequence.duration_ms


def _in_force(command: Command, local_ms: int) -> bool:
    """Whether the command is in force at ``local_ms``, in the time of its sequence."""
    if local_ms < command.at_ms:
        return False
    return command.until_ms is None or local_ms < command.until_ms
