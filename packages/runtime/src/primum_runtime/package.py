"""Loading a deployment package: what the runtime checks before it runs one (decision 0024).

``core`` reads a package and checks that it holds together; it cannot say whether this board
can run it, having neither its drivers nor its profile. That is checked here, all of it before
anything is claimed, and a package that fails any of it is refused whole:

- its board is one this runtime has a profile for;
- its time zone, if it has schedules, is one this system knows;
- every element is of a type with a driver here, and its options are ones its driver and its
  board take (what making its driver checks);
- the elements are wired as the board allows, by the rules ``core`` checks a project with:
  no pin the board lacks, reserves or gives to a bus, no two elements on one pin, PWM only
  where the board has it and one output per channel;
- every event that listens to an element waits for something its driver says the element
  tells (an input turning on or off; an output tells nothing);
- every command asks its element for an action of its driver, with arguments the action
  takes: a value of the parameter's type and within its limits, or a variable that can only
  ever hold such a value.

Nothing trusts a package for having a right hash. The HAL still refuses at the claim what
it can tell, by the pin alone; it knows nothing of reserved pins, so it is not the check.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from primum_core.errors import Location
from primum_core.generated.model import (
    Command,
    Driver,
    DriverAction,
    Package,
    PackageElement,
    PackageVariable,
    parse_hardware,
)
from primum_core.given import limits_within, type_fits
from primum_core.package import read_package
from primum_core.references import LocatedContent
from primum_core.resources import check_resources
from primum_core.values import NUMERIC, Value
from primum_runtime.board import available_boards, load_profile, option_limits
from primum_runtime.drivers import ElementConfig, OptionLimits, create_driver
from primum_runtime.drivers.values import resolve
from primum_runtime.errors import ErrorCode, ErrorParam, PrimumError

log = logging.getLogger(__name__)

# How many problems of a package its error names; the log has them all.
PROBLEMS_SHOWN = 5


@dataclass(frozen=True)
class LoadedPackage:
    """A package this runtime can run: the package, and its elements as the drivers take
    them, each by its id."""

    package: Package
    elements: tuple[ElementConfig, ...]


def load_package(path: Path, manifests: Mapping[str, Driver]) -> LoadedPackage:
    """Read the package at ``path`` and check it against the drivers and its board.

    Fails with ``package.unreadable`` (``path``, ``detail``), ``package.invalid`` (``path``,
    and what ``core`` found: ``problems``, its codes, and ``pointers``, where each is, in the
    same order), ``package.board_unsupported``
    (``board``, ``available``), ``element.type_unsupported``, what making a driver reports
    for an element's options, ``element.wiring_refused`` (``element``, ``pin``, ``problem``:
    the code of what ``core`` found, ``other`` when another element is in the way),
    ``element.action_unknown``, what ``resolve`` reports for the
    arguments of a command, and ``element.variable_unfit`` (``element``, ``action``, ``name``,
    ``variable``) for an argument read from a variable that may not fit.
    """
    try:
        content = path.read_bytes()
    except OSError as error:
        params = {"path": str(path), "detail": str(error)}
        raise PrimumError(ErrorCode.PACKAGE_UNREADABLE, params) from error
    read = read_package(PurePosixPath(path.name), content)
    if read.value is None:
        problems = [
            (str(issue.code), issue.location.pointer if issue.location else "")
            for issue in read.issues
        ]
        for code, pointer in problems:
            log.error("package %s: %s at %r", path, code, pointer)
        shown = problems[:PROBLEMS_SHOWN]
        # The code and the place of each, apart: nobody should have to split a text.
        params = {
            "path": str(path),
            "problems": tuple(code for code, _ in shown),
            "pointers": tuple(pointer for _, pointer in shown),
        }
        raise PrimumError(ErrorCode.PACKAGE_INVALID, params)
    package = read.value
    return LoadedPackage(package, check_against_board(package, manifests))


def check_against_board(
    package: Package, manifests: Mapping[str, Driver]
) -> tuple[ElementConfig, ...]:
    """The elements of a package that holds together, once its board, its elements, their
    wiring and its commands are checked against the drivers and the board's profile.

    Everything wrong is found and logged, not only the first thing: a package is built
    again once, not once per problem. The first is raised."""
    model = package.board.model
    if model not in available_boards():
        params = {"board": model, "available": available_boards()}
        raise PrimumError(ErrorCode.PACKAGE_BOARD_UNSUPPORTED, params)
    limits = option_limits(load_profile(model))
    problems: list[PrimumError] = []
    if package.time_zone is not None and not _is_time_zone(package.time_zone):
        params = {"timeZone": package.time_zone}
        problems.append(PrimumError(ErrorCode.PACKAGE_TIME_ZONE_UNKNOWN, params))
    elements: dict[UUID, ElementConfig] = {}
    for element in package.elements:
        try:
            elements[element.id] = _element(element, manifests, limits)
        except PrimumError as error:
            problems.append(_of(error, element.id))
    problems += wiring_problems(tuple(elements.values()), model)
    variables = {variable.id: variable for variable in package.variables}
    for sequence in package.sequences:
        for command in sequence.commands:
            element = elements.get(command.element)
            if element is None:  # refused above: what is asked of it says nothing more
                continue
            try:
                _check_command(command, element, manifests[element.type], variables)
            except PrimumError as error:
                problems.append(_of(error, command.element))
    for event in package.events:
        if event.element is None or event.trigger is None:
            continue
        listened = elements.get(event.element)
        if listened is None:  # refused above
            continue
        available = tuple(manifests[listened.type].triggers)
        if event.trigger not in available:
            params: dict[str, ErrorParam] = {
                "event": event.name,
                "element": listened.name,
                "trigger": event.trigger,
                "available": available,
            }
            error = PrimumError(ErrorCode.EVENT_NOT_LISTENABLE, params)
            problems.append(_of(error, event.element))
    refuse(problems)
    return tuple(elements.values())


def _is_time_zone(name: str) -> bool:
    """Whether this system knows the time zone: its schedules could not be read otherwise."""
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def refuse(problems: Sequence[PrimumError]) -> None:
    """Log every problem, each once, and raise the first; nothing with none."""
    seen = list(
        dict.fromkeys((problem.code, tuple(problem.params.items())) for problem in problems)
    )
    for code, params in seen:
        log.error("refused: %s", PrimumError(code, dict(params)))
    if problems:
        raise problems[0]


def _of(error: PrimumError, element: UUID) -> PrimumError:
    """The error with the id of the element it is about: a name may be shared."""
    return PrimumError(error.code, {**error.params, "id": str(element)})


def wiring_problems(elements: Sequence[ElementConfig], model: str) -> list[PrimumError]:
    """What ``core`` finds in how the elements are wired to a board of ``model``, by the
    rules it checks a project with (``primum_core.resources``): a pin the board lacks,
    reserves or gives to a bus, two elements on one pin, a PWM output on a pin without
    hardware PWM or on a channel another has. Each an ``element.wiring_refused`` with the
    element, the pin and ``problem``, the code of ``core``'s finding.

    The HAL would refuse some of these at the claim, by the pin alone, and knows nothing of
    reserved pins: here the elements have names."""
    board = UUID(int=0)
    hardware = parse_hardware(
        {
            "id": str(UUID(int=1)),
            "kind": "hardware",
            "schemaVersion": 1,
            "boards": [{"id": str(board), "name": model, "model": model}],
            "elements": [
                {
                    "id": str(UUID(int=index + 2)),
                    "name": element.name,
                    "board": str(board),
                    "type": element.type,
                    "pin": element.pin,
                }
                for index, element in enumerate(elements)
            ],
        }
    )
    located = LocatedContent(hardware, Location(PurePosixPath("package")))
    problems: list[PrimumError] = []
    for issue in check_resources([located], {model: load_profile(model)}):
        index = int(issue.location.pointer.split("/")[2]) if issue.location else 0
        element = elements[index]
        params: dict[str, ErrorParam] = {
            "element": element.name,
            "pin": element.pin,
            "problem": str(issue.code),
        }
        if element.id is not None:
            params["id"] = element.id
        other = issue.params.get("other")
        if isinstance(other, str):
            params["other"] = other
        problems.append(PrimumError(ErrorCode.ELEMENT_WIRING_REFUSED, params))
    return problems


def _element(
    element: PackageElement, manifests: Mapping[str, Driver], limits: OptionLimits
) -> ElementConfig:
    """The element as its driver takes it, its type and its options checked by making one."""
    if element.pin is None:  # core requires the pin of every type it knows: this is another
        params = {"element": element.name, "type": element.type}
        raise PrimumError(ErrorCode.ELEMENT_TYPE_UNSUPPORTED, params)
    options = {option.name: option.value for option in element.config}
    config = ElementConfig(
        element.name, element.type, element.pin, element.active_low, options, str(element.id)
    )
    create_driver(config, manifests, limits)
    return config


def _check_command(
    command: Command,
    element: ElementConfig,
    manifest: Driver,
    variables: Mapping[UUID, PackageVariable],
) -> None:
    action = next((a for a in manifest.actions if a.name == command.action), None)
    if action is None:
        available = tuple(a.name for a in manifest.actions)
        params = {"element": element.name, "action": command.action, "available": available}
        raise PrimumError(ErrorCode.ELEMENT_ACTION_UNKNOWN, params)
    values: dict[str, Value] = {}
    read: set[str] = set()
    for argument in command.arguments:
        if argument.variable is None:
            if argument.value is not None:  # core checked it is one or the other
                values[argument.name] = argument.value
            continue
        read.add(argument.name)
        _check_variable(argument.name, variables[argument.variable], action, element)
    # What is read from a variable was checked above; the rest is checked as any command.
    written = tuple(parameter for parameter in action.parameters if parameter.name not in read)
    resolve(element.name, values, written)


def _check_variable(
    name: str, variable: PackageVariable, action: DriverAction, element: ElementConfig
) -> None:
    """A variable read for a parameter can only hold what the parameter takes: of its type,
    limited within its limits, and never for a parameter that takes only some texts. A number
    that nothing limits is refused as a written one is (``element.value_unlimited``)."""
    parameter = next((p for p in action.parameters if p.name == name), None)
    if parameter is None:
        params = {"element": element.name, "name": name}
        raise PrimumError(ErrorCode.ELEMENT_VALUE_UNKNOWN, params)
    if parameter.type in NUMERIC and (parameter.min is None or parameter.max is None):
        params = {"element": element.name, "name": name}
        raise PrimumError(ErrorCode.ELEMENT_VALUE_UNLIMITED, params)
    fits = (
        type_fits(variable.type, parameter.type)
        and limits_within(variable.min, variable.max, parameter)
        and not parameter.choices
    )
    if not fits:
        params = {
            "element": element.name,
            "action": action.name,
            "name": name,
            "variable": variable.name,
        }
        raise PrimumError(ErrorCode.ELEMENT_VARIABLE_UNFIT, params)
