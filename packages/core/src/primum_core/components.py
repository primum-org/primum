"""Components: sequences with parameters, included by other sequences with arguments.

A block that includes a sequence gives one argument to each of its parameters: an element for
a parameter of type ``element``, a value of the declared type for the others. Sequences that
include each other, directly or through others, can never be flattened: a cycle is an error.
"""

from collections.abc import Iterable, Iterator
from dataclasses import replace
from enum import Enum, auto
from uuid import UUID

from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.generated.model import Argument, Block, Parameter, Sequence
from primum_core.pointers import Step, field_name, pointer
from primum_core.references import LocatedContent
from primum_core.values import check_value

type Sequences = dict[UUID, tuple[Sequence, Location]]


def check_components(files: Iterable[LocatedContent]) -> tuple[Issue, ...]:
    """Arguments that do not fit the parameters of the included sequence, then cycles."""
    sequences: Sequences = {
        file.content.id: (file.content, file.location)
        for file in files
        if isinstance(file.content, Sequence)
    }
    issues: list[Issue] = []
    for sequence, location in sequences.values():
        for index, block in enumerate(sequence.blocks):
            included = sequences.get(block.sequence)
            if included is not None:  # otherwise the references check reports it
                issues += _argument_issues(
                    block.arguments, included[0], ("blocks", index), location
                )
    issues += _cycles(sequences)
    return tuple(issues)


def _at(location: Location, *steps: Step) -> Location:
    return replace(location, pointer=pointer(steps))


def _argument_issues(
    arguments: tuple[Argument, ...], included: Sequence, steps: tuple[Step, ...], location: Location
) -> Iterator[Issue]:
    parameters = {parameter.id: parameter for parameter in included.parameters}
    given: set[UUID] = set()
    for index, argument in enumerate(arguments):
        parameter = parameters.get(argument.parameter)
        if parameter is None:  # not a parameter of this sequence: the references check reports it
            continue
        at = (*steps, "arguments", index)
        if parameter.id in given:
            params = {"parameter": parameter.name}
            yield Issue(CoreErrorCode.ARGUMENT_DUPLICATE, params, _at(location, *at))
            continue
        given.add(parameter.id)
        yield from _shape_issues(argument, parameter, at, location)
    for parameter in included.parameters:
        if parameter.id not in given:
            params = {"parameter": parameter.name}
            yield Issue(CoreErrorCode.ARGUMENT_MISSING, params, _at(location, *steps))


def _shape_issues(
    argument: Argument, parameter: Parameter, steps: tuple[Step, ...], location: Location
) -> Iterator[Issue]:
    """An element parameter takes an element; the others take a value of their type."""
    params = {"parameter": parameter.name}
    wants_element = parameter.type == "element"
    unexpected = "value" if wants_element else "element"
    if (argument.value if wants_element else argument.element) is not None:
        field = {"field": field_name((*steps, unexpected))}
        yield Issue(CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, field, _at(location, *steps, unexpected))
    if wants_element:
        if argument.element is None:
            yield Issue(CoreErrorCode.ARGUMENT_EXPECTED_ELEMENT, params, _at(location, *steps))
    elif argument.value is None:
        yield Issue(CoreErrorCode.ARGUMENT_EXPECTED_VALUE, params, _at(location, *steps))
    else:
        issue = check_value(argument.value, parameter.type, (*steps, "value"), location)
        if issue is not None:
            yield issue


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
