"""Who commands an element at an instant (decision 0017).

The engine (phase 4) will run sequences; this is what it must do, as a pure function that tests
can ask. A sequence that was started commands its elements through its clips, read flattened
(``primum_core.timeline``):

- a clip with a length is in force while it lasts;
- an instant command (a clip of 0 ms) is in force until the next instant command of that
  element in its own sequence, or until its own sequence ends: the block, when it is included;
- a sequence that holds (``whenDone``) stays as it is in its last instant: what is in force
  just before its end stays in force until the sequence is stopped.

Of the commands in force on an element, those of the highest priority count, and among them
the one that started last wins; in a tie, a clip with a length wins over an instant command,
then the sequence given last. With nothing in force, the element is in its safe state.

The caller says which sequences are running and when each started, on its own clock: time
enters as a parameter, as everywhere in ``core``.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from uuid import UUID

from primum_core.errors import Location
from primum_core.generated.model import Clip, Sequence
from primum_core.references import LocatedContent
from primum_core.timeline import FlatClip, duration, flatten_all, holds, sequences_of
from primum_core.workspace import Workspace


@dataclass(frozen=True)
class Running:
    """A sequence that was started and has not been stopped, and when it started (ms)."""

    sequence: UUID
    started_ms: int


@dataclass(frozen=True)
class Command:
    """What an element is asked at an instant: the clip, the running sequence it is from and
    when the command started, on the caller's clock.

    ``settled`` says the action is over and the element stays in the state it ends in: an
    instant command, or a clip that ended with a sequence that holds. Otherwise the action is
    under way since ``since_ms``.
    """

    clip: Clip
    sequence: UUID
    since_ms: int
    settled: bool


@dataclass(frozen=True)
class _Span:
    """A command in the time of its sequence: in force from ``start`` until ``until``, or
    until the sequence is stopped (``None``)."""

    clip: Clip
    start: int
    until: int | None


@dataclass(frozen=True)
class Timeline:
    """A sequence ready to be asked: its priority and the commands of each element."""

    priority: int
    spans: Mapping[UUID, tuple[_Span, ...]]


type Timelines = Mapping[UUID, Timeline]


def timelines_of(workspace: Workspace) -> dict[UUID, Timeline]:
    """Every sequence of a valid project, by id, ready for ``command_at``."""
    files = [
        LocatedContent(file.content, Location(file.path, file_id=file.content.id))
        for file in workspace.files
    ]
    sequences = sequences_of(files)
    flattened = flatten_all(sequences)
    return {
        sequence_id: _timeline(sequence, flattened[sequence_id])
        for sequence_id, (sequence, _) in sequences.items()
    }


def command_at(
    element: UUID, at_ms: int, running: Iterable[Running], timelines: Timelines
) -> Command | None:
    """The command in force on ``element`` at ``at_ms``, or ``None``: its safe state.

    ``running`` are the sequences started and not stopped, in the order they were started;
    each must be one of ``timelines``.
    """
    winner: tuple[tuple[int, int, bool, int], Command] | None = None
    for order, run in enumerate(running):
        timeline = timelines[run.sequence]
        local = at_ms - run.started_ms
        for span in timeline.spans.get(element, ()):
            if local < span.start or (span.until is not None and local >= span.until):
                continue
            length = span.clip.duration_ms
            since = run.started_ms + span.start
            rank = (timeline.priority, since, length > 0, order)
            if winner is None or rank > winner[0]:
                settled = local >= span.start + length
                winner = (rank, Command(span.clip, run.sequence, since, settled))
    return winner[1] if winner else None


def _timeline(sequence: Sequence, clips: list[FlatClip]) -> Timeline:
    end = duration(clips)
    by_element: dict[UUID, list[FlatClip]] = {}
    for clip in clips:
        by_element.setdefault(clip.element, []).append(clip)
    held = holds(sequence)
    return Timeline(
        sequence.priority,
        {
            element: tuple(_span(clip, element_clips, end, held) for clip in element_clips)
            for element, element_clips in by_element.items()
        },
    )


def _span(clip: FlatClip, element_clips: list[FlatClip], end: int, held: bool) -> _Span:
    """When the clip's command stops being in force, among the clips of its element."""
    until = clip.end
    if clip.instant:
        later = [
            other.start
            for other in element_clips
            if other.instant and other.scope == clip.scope and other.start > clip.start
        ]
        until = min(later, default=clip.scope_end)
    # A sequence that holds stays as it is in its last instant.
    return _Span(clip.clip, clip.start, None if held and until == end else until)
