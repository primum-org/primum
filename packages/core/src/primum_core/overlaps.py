"""Sequences that ask one element to do two things at once (decisions 0006 and 0016).

Within a sequence, the clips of one element never overlap in time, the sequences it includes
counted at their offset: an error. A clip of 0 ms, an instant command, holds its instant: no
other clip of its element may start in it. Between sequences, the engine arbitrates (phase 4),
so two sequences that may run at the same time and touch the same element are a warning, unless
they are in one exclusive group (they cancel each other) or on different priorities (one layers
over the other); on an element whose driver is exclusive (one sequence owns it while it runs)
it is an error. Which sequences may run at the same time is approximated statically: those that
automations start.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from itertools import combinations
from uuid import UUID

from primum_core.drivers import Drivers
from primum_core.errors import CoreErrorCode, Issue, Location, Severity
from primum_core.generated.model import Automation, Hardware, Sequence
from primum_core.references import LocatedContent
from primum_core.timeline import FlatClip, Sequences, flatten_all, sequences_of

EXCLUSIVE = "exclusive"


@dataclass(frozen=True)
class _Started:
    """A sequence that automations start, with everything it touches once flattened."""

    sequence: Sequence
    location: Location
    elements: frozenset[UUID]


def check_overlaps(files: Iterable[LocatedContent], drivers: Drivers) -> tuple[Issue, ...]:
    """Clips of one element overlapping within a sequence; sequences that may overlap."""
    files = tuple(files)
    sequences = sequences_of(files)
    names = _names(files, sequences)
    flattened = flatten_all(sequences)
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
    issues += _may_overlap(started, names, _exclusive(files, drivers))
    return tuple(issues)


def _exclusive(files: tuple[LocatedContent, ...], drivers: Drivers) -> frozenset[UUID]:
    """The elements only one sequence can use at a time: those of a driver that says so."""
    return frozenset(
        element.id
        for file in files
        if isinstance(file.content, Hardware)
        for element in file.content.elements
        if (driver := drivers.get(element.type)) is not None and driver.conflict_policy == EXCLUSIVE
    )


def _names(files: tuple[LocatedContent, ...], sequences: Sequences) -> dict[UUID, str]:
    """Elements by id, and parameters by id: what the messages call them."""
    names: dict[UUID, str] = {}
    for file in files:
        if isinstance(file.content, Hardware):
            names.update((element.id, element.name) for element in file.content.elements)
    for sequence, _ in sequences.values():
        names.update((parameter.id, parameter.name) for parameter in sequence.parameters)
    return names


def _clip_overlaps(clips: list[FlatClip], names: Mapping[UUID, str]) -> Iterator[Issue]:
    """Each clip that starts while an earlier clip of its element is still running.

    An element the project does not define is the references check's. Clips that arrive
    through one block on one inner element form a group: their overlaps are the included
    sequence's own, so a clip is only compared with the sequence's own clips and with the other
    groups. Clips reported at one place (a block) are reported once per element, at the first
    overlap: a component of twenty clips included twice is one problem, not twenty.
    """
    by_element: dict[UUID, list[FlatClip]] = {}
    for clip in clips:
        if clip.element in names:
            by_element.setdefault(clip.element, []).append(clip)
    for element, element_clips in by_element.items():
        own_end = 0  # how far the sequence's own clips reach
        group_end: dict[tuple[UUID, UUID | None], int] = {}  # how far each block's clips reach
        reported: set[Location] = set()
        for clip in sorted(element_clips, key=lambda clip: clip.start):
            group = (clip.via, clip.inner) if clip.via is not None else None
            overlapping = own_end > clip.start or any(
                end > clip.start for other, end in group_end.items() if other != group
            )
            if overlapping and clip.at not in reported:
                reported.add(clip.at)
                params = {"element": names[element], "atMs": clip.start}
                yield Issue(CoreErrorCode.TRACK_CLIPS_OVERLAP, params, clip.at)
            if group is None:
                own_end = max(own_end, _busy_until(clip))
            else:
                group_end[group] = max(group_end.get(group, 0), _busy_until(clip))


def _busy_until(clip: FlatClip) -> int:
    """When the element is free for another clip to start. A clip of 0 ms takes its instant:
    one that starts in that same millisecond overlaps it, one that starts in the next does
    not."""
    return max(clip.end, clip.start + 1)


def _started_by_automations(files: tuple[LocatedContent, ...]) -> list[UUID]:
    started: dict[UUID, None] = {}  # in order of first appearance, without repeats
    for file in files:
        if isinstance(file.content, Automation):
            for action in file.content.do:
                if action.action == "start_sequence" and action.sequence is not None:
                    started.setdefault(action.sequence)
    return list(started)


def _concrete(clips: list[FlatClip], parameters: set[UUID]) -> frozenset[UUID]:
    """The elements the clips touch. A parameter bound to nothing (the sequence's own, or one of
    a component included without that argument) is not an element."""
    return frozenset(clip.element for clip in clips if clip.element not in parameters)


def _may_overlap(
    started: list[_Started], names: Mapping[UUID, str], exclusive: frozenset[UUID]
) -> Iterator[Issue]:
    """Pairs of started sequences on one priority, not in one exclusive group, sharing an element.

    Reported once, at the second sequence by path, naming the first shared element: an error
    if one of the shared elements is exclusive (that one is named), a warning otherwise.
    """
    for first, second in combinations(sorted(started, key=lambda s: s.location.path), 2):
        if first.sequence.priority != second.sequence.priority:
            continue
        group = first.sequence.exclusive_group
        if group is not None and group == second.sequence.exclusive_group:
            continue
        # An element the project does not define is the references check's.
        shared = [element for element in first.elements & second.elements if element in names]
        if not shared:
            continue
        owned = sorted(names[element] for element in shared if element in exclusive)
        params = {
            "sequence": second.sequence.name,
            "other": first.sequence.name,
            "element": owned[0] if owned else min(names[element] for element in shared),
        }
        if owned:
            yield Issue(CoreErrorCode.SEQUENCE_EXCLUSIVE_ELEMENT_SHARED, params, second.location)
        else:
            code = CoreErrorCode.SEQUENCE_MAY_OVERLAP
            yield Issue(code, params, second.location, Severity.WARNING)
