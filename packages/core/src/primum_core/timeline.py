"""Sequences in time: every clip of a sequence and of what it includes, at its offset.

A clip runs in the time of its sequence; a block runs the included sequence from its ``atMs``,
its parameters bound to the block's arguments. The checks that need to know what a sequence
really asks of each element (clips that overlap, actions the element cannot do) work on the
sequence **flattened**: its own clips plus the clips of what it includes, each sequence
flattened once.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from uuid import UUID

from primum_core.errors import Location
from primum_core.generated.model import Clip, Sequence
from primum_core.pointers import Step, pointer
from primum_core.references import LocatedContent

type Sequences = Mapping[UUID, tuple[Sequence, Location]]
type Flattened = Mapping[UUID, list["FlatClip"]]
type Bindings = Mapping[UUID, UUID]  # a parameter → the element given for it


@dataclass(frozen=True)
class FlatClip:
    """A clip in the flattened time of a sequence: from ``start`` to ``end`` on ``element``.

    ``element`` is a concrete element, or a parameter of the sequence being flattened. ``at`` is
    where to report it: the clip itself, or the block that includes the sequence it comes from;
    ``via`` is that block, ``None`` for the sequence's own clips, and ``inner`` the element as
    the included sequence saw it, before the block bound its parameters. ``clip`` is the clip
    as written: its action and arguments.
    """

    element: UUID
    start: int
    end: int
    at: Location
    clip: Clip
    via: UUID | None = None
    inner: UUID | None = None

    @property
    def bound_here(self) -> bool:
        """Whether the block gave this clip its element: what the included sequence could not
        know, so what is new, and reported, here."""
        return self.via is not None and self.inner != self.element


def at(location: Location, *steps: Step) -> Location:
    return replace(location, pointer=pointer(steps))


def sequences_of(files: Iterable[LocatedContent]) -> dict[UUID, tuple[Sequence, Location]]:
    """Every sequence of the project with its file, by id."""
    return {
        file.content.id: (file.content, file.location)
        for file in files
        if isinstance(file.content, Sequence)
    }


def flatten_all(sequences: Sequences) -> dict[UUID, list[FlatClip]]:
    """Every clip of each sequence and of what it includes, in the sequence's own time.

    Clips that come through a block are reported at that block. Parameters stay as they are:
    the sequence that includes a component binds them (``_compose``). Each sequence is flattened
    once, after the ones it includes, by a walk with its own stack: no recursion, however deep
    the inclusions. A loop of inclusions is skipped here: the components check reports it, so
    the project is invalid anyway; until then the sequences in the loop are flattened without
    the clips that come back through it, and so are the sequences that include them.
    """
    flattened: dict[UUID, list[FlatClip]] = {}
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


def _compose(sequence_id: UUID, sequences: Sequences, flattened: Flattened) -> list[FlatClip]:
    """The clips of one sequence: its own, and the included ones shifted and bound."""
    sequence, location = sequences[sequence_id]
    clips: list[FlatClip] = []
    for track_index, track in enumerate(sequence.tracks):
        for index, clip in enumerate(track.clips):
            place = at(location, "tracks", track_index, "clips", index)
            end = clip.at_ms + clip.duration_ms
            clips.append(FlatClip(track.element, clip.at_ms, end, place, clip))
    for index, block in enumerate(sequence.blocks):
        included = flattened.get(block.sequence)  # absent: unknown, or a loop
        if included is None:
            continue
        bindings: Bindings = {
            argument.parameter: argument.element
            for argument in block.arguments
            if argument.element is not None
        }
        place = at(location, "blocks", index)
        clips += [
            FlatClip(
                bindings.get(clip.element, clip.element),
                clip.start + block.at_ms,
                clip.end + block.at_ms,
                place,
                clip.clip,
                block.id,
                clip.element,
            )
            for clip in included
        ]
    return clips
