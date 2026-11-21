"""Components: sequences with parameters, included by other sequences with arguments.

A block that includes a sequence gives one argument to each of its parameters: an element for
a parameter of type ``element``; for the others a value of the declared type, written or taken
from a name (``valueOf``, decision 0024). Sequences that include each other, directly or
through others, can never be flattened: a cycle is an error. A component is only ever
included: an automation cannot start or stop one, having nothing to give its parameters.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from enum import Enum, auto
from uuid import UUID

from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.generated.model import Argument, Automation, Block, Parameter, Sequence
from primum_core.given import Fixed, FromVariable, Unbound, type_fits
from primum_core.pointers import Step, field_name, pointer
from primum_core.references import LocatedContent
from primum_core.sources import Names
from primum_core.timeline import NameRef
from primum_core.values import EXPECTED, check_value

type Sequences = dict[UUID, tuple[Sequence, Location]]


def check_components(files: Iterable[LocatedContent]) -> tuple[Issue, ...]:
    """Arguments that do not fit the parameters of the included sequence, automations that
    start a component, then cycles."""
    files = tuple(files)
    sequences: Sequences = {
        file.content.id: (file.content, file.location)
        for file in files
        if isinstance(file.content, Sequence)
    }
    names = Names(files)
    issues: list[Issue] = []
    for sequence, location in sequences.values():
        for index, block in enumerate(sequence.blocks):
            included = sequences.get(block.sequence)
            if included is not None:  # otherwise the references check reports it
                given = _Given(block.arguments, sequence.id, names)
                issues += _argument_issues(given, included[0], ("blocks", index), location)
    for file in files:
        if isinstance(file.content, Automation):
            issues += _started_components(file.content, file.location, sequences)
    issues += _cycles(sequences)
    return tuple(issues)


@dataclass(frozen=True)
class _Given:
    """The arguments of a block, the sequence the block is in and what its names stand for."""

    arguments: tuple[Argument, ...]
    including: UUID
    names: Names


def _started_components(
    automation: Automation, location: Location, sequences: Sequences
) -> Iterator[Issue]:
    for index, action in enumerate(automation.do):
        named = sequences.get(action.sequence) if action.sequence is not None else None
        if named is not None and named[0].parameters:
            params = {"sequence": named[0].name}
            at = _at(location, "do", index, "sequence")
            yield Issue(CoreErrorCode.AUTOMATION_STARTS_COMPONENT, params, at)


def _at(location: Location, *steps: Step) -> Location:
    return replace(location, pointer=pointer(steps))


def _argument_issues(
    block: _Given, included: Sequence, steps: tuple[Step, ...], location: Location
) -> Iterator[Issue]:
    parameters = {parameter.id: parameter for parameter in included.parameters}
    given: set[UUID] = set()
    for index, argument in enumerate(block.arguments):
        parameter = parameters.get(argument.parameter)
        if parameter is None:  # not a parameter of this sequence: the references check reports it
            continue
        at = (*steps, "arguments", index)
        if parameter.id in given:
            params = {"parameter": parameter.name}
            yield Issue(CoreErrorCode.ARGUMENT_DUPLICATE, params, _at(location, *at))
            continue
        given.add(parameter.id)
        yield from _shape_issues(argument, parameter, at, location, block)
    for parameter in included.parameters:
        if parameter.id not in given:
            params = {"parameter": parameter.name}
            yield Issue(CoreErrorCode.ARGUMENT_MISSING, params, _at(location, *steps))


def _shape_issues(
    argument: Argument,
    parameter: Parameter,
    steps: tuple[Step, ...],
    location: Location,
    block: _Given,
) -> Iterator[Issue]:
    """An element parameter takes an element; the others take a value of their type, written
    or taken from a name."""
    params = {"parameter": parameter.name}
    present = {
        "element": argument.element is not None,
        "value": argument.value is not None,
        "valueOf": argument.value_of is not None,
    }
    wants_element = parameter.type == "element"
    unexpected = ["value", "valueOf"] if wants_element else ["element"]
    if present["value"] and present["valueOf"] and not wants_element:
        unexpected.append("valueOf")
    for field in unexpected:
        if present[field]:
            params_field = {"field": field_name((*steps, field))}
            at = _at(location, *steps, field)
            yield Issue(CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, params_field, at)
    if wants_element:
        if argument.element is None:
            yield Issue(CoreErrorCode.ARGUMENT_EXPECTED_ELEMENT, params, _at(location, *steps))
    elif argument.value is not None:
        issue = check_value(argument.value, parameter.type, (*steps, "value"), location)
        if issue is not None:
            yield issue
    elif argument.value_of is not None:
        yield from _name_issues(argument.value_of, parameter, (*steps, "valueOf"), location, block)
    else:
        yield Issue(CoreErrorCode.ARGUMENT_EXPECTED_VALUE, params, _at(location, *steps))


def _name_issues(
    name: str, parameter: Parameter, steps: tuple[Step, ...], location: Location, block: _Given
) -> Iterator[Issue]:
    """A name given to a value parameter stands for a value of the parameter's type. One that
    stands for nothing is the scopes check's."""
    source = block.names.of(NameRef(name, block.including))
    match source:
        case None:
            return
        case Fixed(value):
            issue = check_value(value, parameter.type, steps, location)
            if issue is not None:
                yield issue
        case FromVariable(value_type=value_type) | Unbound(value_type=value_type):
            if not type_fits(value_type, parameter.type):
                field = {"field": field_name(steps)}
                yield Issue(EXPECTED[parameter.type], field, _at(location, *steps))


class _Visit(Enum):
    IN_PROGRESS = auto()
    DONE = auto()


def _cycles(sequences: Sequences) -> list[Issue]:
    """One issue per block that closes a cycle of inclusions, found by a depth-first walk.

    The walk keeps its own stack instead of recursing, so a chain of inclusions as long as a
    project cares to make never exhausts the interpreter's.
    """
    issues: list[Issue] = []
    state: dict[UUID, _Visit] = {}
    path: list[UUID] = []
    # The blocks of each sequence on the path that are still to be looked at.
    pending: list[Iterator[tuple[int, Block]]] = []

    def enter(sequence_id: UUID) -> None:
        state[sequence_id] = _Visit.IN_PROGRESS
        path.append(sequence_id)
        pending.append(iter(enumerate(sequences[sequence_id][0].blocks)))

    for root in sequences:
        if root in state:
            continue
        enter(root)
        while path:
            step = next(pending[-1], None)
            if step is None:
                state[path.pop()] = _Visit.DONE
                pending.pop()
                continue
            index, block = step
            target = block.sequence
            if target not in sequences:
                continue
            if state.get(target) is _Visit.IN_PROGRESS:
                location = sequences[path[-1]][1]
                issues.append(_cycle_issue(path, target, sequences, _at(location, "blocks", index)))
            elif target not in state:
                enter(target)
    return issues


def _cycle_issue(path: list[UUID], target: UUID, sequences: Sequences, at: Location) -> Issue:
    """``path`` ends in the sequence whose block includes ``target``, already on the path."""
    current = sequences[path[-1]][0].name
    through = tuple(sequences[step][0].name for step in path[path.index(target) : -1])
    if not through:
        return Issue(CoreErrorCode.SEQUENCE_INCLUDES_ITSELF, {"sequence": current}, at)
    return Issue(CoreErrorCode.SEQUENCE_CYCLE, {"sequence": current, "chain": through}, at)
