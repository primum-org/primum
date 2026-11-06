"""Ids and references between the files of a project (decision 0004).

Every file has an id, and so has everything defined inside one that others can refer to
(boards, elements, constants, variables, parameters, clips, blocks). Ids are unique in the
whole project. A reference is an id, and it must name something of the right kind: a track
plays an element, an automation starts a sequence. A track may also play an element parameter
of its own sequence (a component), and an event comes from an input element, never an output.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from uuid import UUID

from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.formats import ProjectFileContent
from primum_core.generated.model import (
    Automation,
    Event,
    Hardware,
    Sequence,
    Variables,
)
from primum_core.pointers import Step, field_name, pointer


@dataclass(frozen=True)
class LocatedContent:
    """A file's content and where it is: what the checks of a project work on."""

    content: ProjectFileContent
    location: Location


@dataclass(frozen=True)
class _Entity:
    kind: str
    location: Location
    owner: UUID | None = None  # the sequence of a parameter
    variant: str | None = None  # the type of an element or of a parameter


@dataclass(frozen=True)
class _Reference:
    target: UUID
    kinds: frozenset[str]
    steps: tuple[Step, ...]
    location: Location
    # A parameter is accepted only if it belongs to this sequence.
    parameter_of: UUID | None = None
    # For some kinds, only these types (an element parameter, an input element).
    variants: Mapping[str, frozenset[str]] | None = None


INPUT_ELEMENT = frozenset({"element"})
INPUT_TYPES = {"element": frozenset({"digital_input", "i2c_device"})}
OWN_ELEMENT = frozenset({"element", "parameter"})
ELEMENT_PARAMETER = {"parameter": frozenset({"element"})}
PARAMETER = frozenset({"parameter"})


def check_references(
    files: Iterable[LocatedContent], manifest: tuple[UUID, Location] | None = None
) -> tuple[Issue, ...]:
    """Duplicate ids, then every reference that names nothing, or something of another kind."""
    files = tuple(files)
    index: dict[UUID, _Entity] = {}
    issues: list[Issue] = []
    entities: list[tuple[UUID, _Entity]] = []
    if manifest is not None:
        entities.append((manifest[0], _Entity("project", manifest[1])))
    entities += (entity for file in files for entity in _entities(file))
    for id_, entity in entities:
        if id_ in index:
            issues.append(Issue(CoreErrorCode.ID_DUPLICATE, {"id": str(id_)}, entity.location))
        else:
            index[id_] = entity
    for file in files:
        for reference in _references(file):
            issue = _check(reference, index)
            if issue is not None:
                issues.append(issue)
    return tuple(issues)


def _check(reference: _Reference, index: dict[UUID, _Entity]) -> Issue | None:
    entity = index.get(reference.target)
    if entity is None:
        code = CoreErrorCode.REF_UNKNOWN
    elif _fits(entity, reference):
        return None
    else:
        code = CoreErrorCode.REF_WRONG_KIND
    params = {"field": field_name(reference.steps), "id": str(reference.target)}
    return Issue(code, params, replace(reference.location, pointer=pointer(reference.steps)))


def _fits(entity: _Entity, reference: _Reference) -> bool:
    if entity.kind not in reference.kinds:
        return False
    if entity.kind == "parameter" and entity.owner != reference.parameter_of:
        return False
    allowed = (reference.variants or {}).get(entity.kind)
    return allowed is None or entity.variant in allowed


def _at(file: LocatedContent, *steps: Step) -> Location:
    return replace(file.location, pointer=pointer(steps))


def _entities(file: LocatedContent) -> Iterator[tuple[UUID, _Entity]]:
    content = file.content
    yield content.id, _Entity(content.kind, file.location)
    match content:
        case Hardware():
            for index, board in enumerate(content.boards):
                yield board.id, _Entity("board", _at(file, "boards", index))
            for index, element in enumerate(content.elements):
                at = _at(file, "elements", index)
                yield element.id, _Entity("element", at, variant=element.type)
        case Variables():
            for index, constant in enumerate(content.constants):
                yield constant.id, _Entity("constant", _at(file, "constants", index))
            for index, variable in enumerate(content.variables):
                yield variable.id, _Entity("variable", _at(file, "variables", index))
        case Sequence():
            for index, parameter in enumerate(content.parameters):
                at = _at(file, "parameters", index)
                yield parameter.id, _Entity("parameter", at, content.id, parameter.type)
            for track_index, track in enumerate(content.tracks):
                for index, clip in enumerate(track.clips):
                    yield clip.id, _Entity("clip", _at(file, "tracks", track_index, "clips", index))
            for index, block in enumerate(content.blocks):
                yield block.id, _Entity("block", _at(file, "blocks", index))
        case _:
            pass


def _references(file: LocatedContent) -> Iterator[_Reference]:
    content = file.content
    at = file.location
    match content:
        case Hardware():
            for index, element in enumerate(content.elements):
                yield _Reference(
                    element.board, frozenset({"board"}), ("elements", index, "board"), at
                )
        case Variables():
            for index, imported in enumerate(content.imports):
                steps = ("imports", index, "from")
                yield _Reference(imported.from_, frozenset({"variables"}), steps, at)
        case Sequence():
            yield from _sequence_references(content, at)
        case Event():
            if content.element is not None:
                steps = ("element",)
                yield _Reference(content.element, INPUT_ELEMENT, steps, at, None, INPUT_TYPES)
        case Automation():
            for index, trigger in enumerate(content.when):
                yield _Reference(trigger, frozenset({"event", "schedule"}), ("when", index), at)
            for index, action in enumerate(content.do):
                if action.sequence is not None:
                    steps = ("do", index, "sequence")
                    yield _Reference(action.sequence, frozenset({"sequence"}), steps, at)
        case _:
            pass


def _sequence_references(sequence: Sequence, at: Location) -> Iterator[_Reference]:
    own = sequence.id
    for index, track in enumerate(sequence.tracks):
        steps = ("tracks", index, "element")
        yield _Reference(track.element, OWN_ELEMENT, steps, at, own, ELEMENT_PARAMETER)
    for index, block in enumerate(sequence.blocks):
        yield _Reference(block.sequence, frozenset({"sequence"}), ("blocks", index, "sequence"), at)
        for argument_index, argument in enumerate(block.arguments):
            steps: tuple[Step, ...] = ("blocks", index, "arguments", argument_index)
            # A parameter of the included sequence, not of any other.
            yield _Reference(
                argument.parameter, PARAMETER, (*steps, "parameter"), at, block.sequence
            )
            if argument.element is not None:
                yield _Reference(
                    argument.element, OWN_ELEMENT, (*steps, "element"), at, own, ELEMENT_PARAMETER
                )
