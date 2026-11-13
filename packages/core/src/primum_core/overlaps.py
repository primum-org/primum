"""Sequences that ask one element to do two things at once (decisions 0006, 0016 and 0017).

Within a sequence, two clips with a length of one element never overlap in time, the sequences
it includes counted at their offset: an error. Two instant commands of one element in one
instant are an error too: which of them stands? An instant command and a clip with a length do
not compete (the one that started last commands, decision 0017), so they may share a moment.
Between sequences, the engine arbitrates (phase 4), so two sequences that may run at the same
time and touch the same element are a warning, unless they are in one exclusive group (they
cancel each other) or on different priorities (one layers over the other); on an element whose
driver is exclusive (one sequence owns it while it runs) it is an error. Which sequences may run
at the same time is approximated statically: those that automations start.

An instant command lasts until its own sequence ends, so one that is the last thing of its
sequence is never seen: a warning, unless the sequence holds.
"""

from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from itertools import combinations
from uuid import UUID

from primum_core.drivers import Drivers
from primum_core.errors import CoreErrorCode, Issue, Location, Severity
from primum_core.generated.model import Automation, Driver, Hardware, Sequence
from primum_core.references import LocatedContent
from primum_core.timeline import FlatClip, Sequences, duration, flatten_all, holds, sequences_of

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
    started_ids = [
        sequence_id for sequence_id in _started_by_automations(files) if sequence_id in sequences
    ]
    started = [
        _Started(*sequences[sequence_id], _concrete(flattened[sequence_id], parameters))
        for sequence_id in started_ids
    ]
    element_drivers = _drivers_of_elements(files, drivers)
    issues += _may_overlap(started, names, _exclusive(element_drivers))
    for sequence_id, (sequence, _) in sequences.items():
        included = {
            block.id: sequences[block.sequence][0].name
            for block in sequence.blocks
            if block.sequence in sequences
        }
        clips = flattened[sequence_id]
        issues += _unseen_instants(sequence, included, clips, names, element_drivers)
    return tuple(issues)


def _drivers_of_elements(
    files: tuple[LocatedContent, ...], drivers: Drivers
) -> dict[UUID, Driver | None]:
    """Every element of the project with the driver of its type, if its type has one."""
    return {
        element.id: drivers.get(element.type)
        for file in files
        if isinstance(file.content, Hardware)
        for element in file.content.elements
    }


def _exclusive(element_drivers: Mapping[UUID, Driver | None]) -> frozenset[UUID]:
    """The elements only one sequence can use at a time: those of a driver that says so."""
    return frozenset(
        element
        for element, driver in element_drivers.items()
        if driver is not None and driver.conflict_policy == EXCLUSIVE
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
    """Each clip that starts while an earlier clip of its element is still running. Clips with
    a length are compared with each other, and so are instant commands, never one with the
    other.

    An element the project does not define is the references check's. Clips that arrive
    through one block on one inner element form a group: their overlaps are the included
    sequence's own, so a clip is only compared with the sequence's own clips and with the other
    groups. Clips reported at one place (a block) are reported once per element, at the first
    overlap: a component of twenty clips included twice is one problem, not twenty.
    """
    by_element: dict[tuple[UUID, bool], list[FlatClip]] = {}
    for clip in clips:
        if clip.element in names:
            by_element.setdefault((clip.element, clip.instant), []).append(clip)
    for (element, _), element_clips in by_element.items():
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
    """When the element is free for another clip of the same kind to start. An instant command
    takes its instant: another in that same millisecond overlaps it, one in the next does
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


def _unseen_instants(
    sequence: Sequence,
    included: Mapping[UUID, str],
    clips: list[FlatClip],
    names: Mapping[UUID, str],
    element_drivers: Mapping[UUID, Driver | None],
) -> Iterator[Issue]:
    """Instant commands that are the last thing of their own sequence: it ends there, so what
    they ask is never seen, started on its own or included (``included``: the name of the
    sequence each block includes).

    Each is reported once, where its element is known: in its own sequence, or at the block
    that gives a component its element. Left alone: what a sequence that holds keeps as it is
    in its last instant; an instant command that asks for its element's safe state after
    something else (an instant ``on``, and an instant ``off`` to end with: that is where the
    element goes anyway); and two of one element in that instant, which overlap: that error is
    enough.
    """
    end = duration(clips)
    last = [
        clip
        for clip in clips
        if clip.instant
        and clip.start == clip.scope_end
        and not (holds(sequence) and clip.scope_end == end)
        and (clip.via is None or clip.bound_here)
    ]
    together = Counter((clip.scope, clip.element) for clip in last)
    for clip in last:
        if together[clip.scope, clip.element] > 1 or clip.element not in element_drivers:
            continue
        driver = element_drivers[clip.element]
        # A track on an element that takes no clips, and an action its driver does not have,
        # are the actions check's.
        if driver is None or clip.clip.action not in {action.name for action in driver.actions}:
            continue
        lasts_no_time = clip.via is None and end == 0
        if clip.clip.action == driver.safe_state and not lasts_no_time:
            continue
        params = {
            "sequence": sequence.name if clip.via is None else included[clip.via],
            "element": names[clip.element],
            "action": clip.clip.action,
        }
        yield Issue(CoreErrorCode.CLIP_INSTANT_AT_END, params, clip.at, Severity.WARNING)
