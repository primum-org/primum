"""Loading a deployment package: what the runtime checks before it runs one (decision 0024).

``core`` reads a package and checks that it holds together; it cannot say whether this board
can run it, having neither its drivers nor its profile. That is checked here, all of it before
anything is claimed, and a package that fails any of it is refused whole:

- its board is one this runtime has a profile for;
- every element is of a type with a driver here, and its options are ones its driver and its
  board take (what making its driver checks); no two elements are on one pin;
- every command asks its element for an action of its driver, with arguments the action
  takes: a value of the parameter's type and within its limits, or a variable that can only
  ever hold such a value.

Nothing trusts a package for having a right hash. The HAL is the last word on the pins, when
it claims them (a pin the board lacks or reserves, a PWM channel two pins share): what can be
told here is told here, where the elements have names.
"""

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import UUID

from primum_core.generated.model import (
    Command,
    Driver,
    DriverAction,
    Package,
    PackageElement,
    PackageVariable,
)
from primum_core.given import limits_within, type_fits
from primum_core.package import read_package
from primum_core.values import NUMERIC, Value
from primum_runtime.board import available_boards, load_profile, option_limits
from primum_runtime.drivers import ElementConfig, OptionLimits, create_driver
from primum_runtime.drivers.values import resolve
from primum_runtime.errors import ErrorCode, PrimumError

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
    for an element's options, ``package.pin_shared`` (``pin``, ``elements``: the names of the
    two), ``element.action_unknown``, what ``resolve`` reports for the
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
    """The elements of a package that holds together, once its board, its elements and its
    commands are checked against the drivers and the board's profile."""
    model = package.board.model
    if model not in available_boards():
        params = {"board": model, "available": available_boards()}
        raise PrimumError(ErrorCode.PACKAGE_BOARD_UNSUPPORTED, params)
    limits = option_limits(load_profile(model))
    elements = {element.id: _element(element, manifests, limits) for element in package.elements}
    _check_pins(elements.values())
    variables = {variable.id: variable for variable in package.variables}
    for sequence in package.sequences:
        for command in sequence.commands:
            element = elements[command.element]  # core checked the reference
            _check_command(command, element, manifests[element.type], variables)
    return tuple(elements.values())


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


def _check_pins(elements: Iterable[ElementConfig]) -> None:
    """No two elements on one pin. The HAL would refuse the claim, but by the pin alone."""
    on_pin: dict[int, ElementConfig] = {}
    for element in elements:
        other = on_pin.setdefault(element.pin, element)
        if other is not element:
            params = {"pin": element.pin, "elements": (other.name, element.name)}
            raise PrimumError(ErrorCode.PACKAGE_PIN_SHARED, params)


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
