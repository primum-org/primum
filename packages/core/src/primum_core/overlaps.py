"""Sequences that ask one element to do two things at once (decision 0006).

Within a sequence, the clips of one element never overlap in time, the sequences it includes
counted at their offset: an error. Between sequences, the engine arbitrates (phase 4), so two
sequences that may run at the same time and touch the same element are a warning, unless they
are in one exclusive group (they cancel each other) or on different priorities (one layers over
the other). Which sequences may run at the same time is approximated statically: those that
automations start.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from itertools import combinations
from uuid import UUID

from primum_core.errors import CoreErrorCode, Issue, Location, Severity
from primum_core.generated.model import Automation, Hardware, Sequence
from primum_core.pointers import Step, pointer
from primum_core.references import LocatedContent

type Sequences = Mapping[UUID, tuple[Sequence, Location]]
type Flattened = Mapping[UUID, list["_Clip"]]
type Bindings = Mapping[UUID, UUID]  # a parameter → the element given for it


@dataclass(frozen=True)
class _Clip:
    """A clip in the flattened time of a sequence: ``[start, end)`` on ``element``.

    ``element`` is a concrete element, or a parameter of the sequence being flattened. ``at`` is
    where to report it: the clip itself, or the block that includes the sequence it comes from;
    ``via`` is that block, ``None`` for the sequence's own clips, and ``inner`` the element as
    the included sequence saw it, before the block bound its parameters. Two clips that come
    through one block on one inner element overlap inside the included sequence, which is where
    that is reported; two that only meet because the block bound a parameter to an element the
    other already used are new here.
    """

    element: UUID
    start: int
    end: int
    at: Location
    via: UUID | None = None
    inner: UUID | None = None


@dataclass(frozen=True)
class _Started:
    """A sequence that automations start, with everything it touches once flattened."""

    sequence: Sequence
    location: Location
    elements: frozenset[UUID]


def check_overlaps(files: Iterable[LocatedContent]) -> tuple[Issue, ...]:
    """Clips of one element overlapping within a sequence; sequences that may overlap."""
    files = tuple(files)
    sequences: Sequences = {
        file.content.id: (file.content, file.location)
        for file in files
        if isinstance(file.content, Sequence)
    }
    names = _names(files, sequences)
    flattened = _flatten_all(sequences)
    issues: list[Issue] = []
    for sequence_id in sequences:
        issues += _clip_overlaps(flattened[sequence_id], names)
    parameters = {
        parameter.id for sequence, _ in sequences.values() for parameter in sequence.parameters
    }
    started = [
        _Started(*sequences[sequence_id], _concrete(flattened[sequence_id], parameters))
        for sequence_id in _started_by_automations(files)
        if sequence_id in sequences
    ]
    issues += _may_overlap(started, names)
    return tuple(issues)


def _names(files: tuple[LocatedContent, ...], sequences: Sequences) -> dict[UUID, str]:
    """Elements by id, and parameters by id: what the messages call them."""
    names: dict[UUID, str] = {}
    for file in files:
        if isinstance(file.content, Hardware):
            names.update((element.id, element.name) for element in file.content.elements)
    for sequence, _ in sequences.values():
        names.update((parameter.id, parameter.name) for parameter in sequence.parameters)
    return names


def _at(location: Location, *steps: Step) -> Location:
    return replace(location, pointer=pointer(steps))


def _flatten_all(sequences: Sequences) -> dict[UUID, list[_Clip]]:
    """Every clip of each sequence and of what it includes, in the sequence's own time.

    Clips that come through a block are reported at that block. Parameters stay as they are:
    the sequence that includes a component binds them (``_compose``). Each sequence is flattened
    once, after the ones it includes, by a walk with its own stack: no recursion, however deep
    the inclusions. A loop of inclusions is skipped here: the components check reports it.
    """
    flattened: dict[UUID, list[_Clip]] = {}
    for root in sequences:
        stack = [root]
        in_progress: set[UUID] = set()
        while stack:
            sequence_id = stack[-1]
            if sequence_id in flattened:
                stack.pop()
                continue
            if sequence_id not in in_progress:
                in_progress.add(sequence_id)
                pending = [
                    block.sequence
                    for block in sequences[sequence_id][0].blocks
                    if block.sequence in sequences
                    and block.sequence not in flattened
                    and block.sequence not in in_progress
                ]
                if pending:
                    stack += pending
                    continue
            flattened[sequence_id] = _compose(sequence_id, sequences, flattened)
            in_progress.discard(sequence_id)
            stack.pop()
    return flattened


def _compose(sequence_id: UUID, sequences: Sequences, flattened: Flattened) -> list[_Clip]:
    """The clips of one sequence: its own, and the included ones shifted and bound."""
    sequence, location = sequences[sequence_id]
    clips: list[_Clip] = []
    for track_index, track in enumerate(sequence.tracks):
        for index, clip in enumerate(track.clips):
            if clip.duration_ms == 0:  # takes no time: cannot overlap anything
                continue
            at = _at(location, "tracks", track_index, "clips", index)
            clips.append(_Clip(track.element, clip.at_ms, clip.at_ms + clip.duration_ms, at))
    for index, block in enumerate(sequence.blocks):
        included = flattened.get(block.sequence)  # absent: unknown, or a loop
        if included is None:
            continue
        bindings: Bindings = {
            argument.parameter: argument.element
            for argument in block.arguments
            if argument.element is not None
        }
        at = _at(location, "blocks", index)
        clips += [
            _Clip(
                bindings.get(clip.element, clip.element),
                clip.start + block.at_ms,
                clip.end + block.at_ms,
                at,
                block.id,
                clip.element,
            )
            for clip in included
        ]
    return clips


def _clip_overlaps(clips: list[_Clip], names: Mapping[UUID, str]) -> Iterator[Issue]:
    """Each clip that starts while an earlier clip of its element is still running.

    An element the project does not define is the references check's. Clips that arrive
    through one block on one inner element form a group: their overlaps are the included
    sequence's own, so a clip is only compared with the sequence's own clips and with the other
    groups. Clips reported at one place (a block) are reported once per element, at the first
    overlap: a component of twenty clips included twice is one problem, not twenty.
    """
    by_element: dict[UUID, list[_Clip]] = {}
    for clip in clips:
        if clip.element in names:
            by_element.setdefault(clip.element, []).append(clip)
    for element, own in by_element.items():
        own_end = 0  # how far the sequence's own clips reach
        group_end: dict[tuple[UUID, UUID | None], int] = {}  # how far each block's clips reach
        reported: set[Location] = set()
        for clip in sorted(own, key=lambda clip: clip.start):
            group = (clip.via, clip.inner) if clip.via is not None else None
            overlapping = own_end > clip.start or any(
                end > clip.start for other, end in group_end.items() if other != group
            )
            if overlapping and clip.at not in reported:
                reported.add(clip.at)
                params = {"element": names[element], "atMs": clip.start}
                yield Issue(CoreErrorCode.TRACK_CLIPS_OVERLAP, params, clip.at)
            if group is None:
                own_end = max(own_end, clip.end)
            else:
                group_end[group] = max(group_end.get(group, 0), clip.end)


def _started_by_automations(files: tuple[LocatedContent, ...]) -> list[UUID]:
    started: dict[UUID, None] = {}  # in order of first appearance, without repeats
    for file in files:
        if isinstance(file.content, Automation):
            for action in file.content.do:
                if action.action == "start_sequence" and action.sequence is not None:
                    started.setdefault(action.sequence)
    return list(started)


def _concrete(clips: list[_Clip], parameters: set[UUID]) -> frozenset[UUID]:
    """The elements the clips touch. A parameter bound to nothing (the sequence's own, or one of
    a component included without that argument) is not an element."""
    return frozenset(clip.element for clip in clips if clip.element not in parameters)


def _may_overlap(started: list[_Started], names: Mapping[UUID, str]) -> Iterator[Issue]:
    """Pairs of started sequences on one priority, not in one exclusive group, sharing an element.

    Reported once, at the second sequence by path, naming the first shared element.
    """
    for first, second in combinations(sorted(started, key=lambda s: s.location.path), 2):
        if first.sequence.priority != second.sequence.priority:
            continue
        group = first.sequence.exclusive_group
        if group is not None and group == second.sequence.exclusive_group:
            continue
        # An element the project does not define is the references check's.
        shared = sorted(names[e] for e in first.elements & second.elements if e in names)
        if not shared:
            continue
        params = {
            "sequence": second.sequence.name,
            "other": first.sequence.name,
            "element": shared[0],
        }
        yield Issue(CoreErrorCode.SEQUENCE_MAY_OVERLAP, params, second.location, Severity.WARNING)
