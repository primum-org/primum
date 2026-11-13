"""Driver manifests: what one means beyond its schema.

A manifest (``drivers/<elementType>.json``) describes a driver as data: the actions a clip may
ask of its elements, each with its parameters, and the options an element of its type takes
in a ``.hw`` file (its configuration). Its schema checks the shape; ``check_driver`` checks
what the shape cannot say. Callers read the file and use ``primum_core.formats.read_driver``,
which runs it, and pass the manifests, by element type, to the workspace loader. What a project
gives those parameters is checked in ``primum_core.given``.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import replace

from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.generated.model import Driver, DriverParameter
from primum_core.given import limits, within
from primum_core.pointers import Step, field_name, pointer
from primum_core.values import EXPECTED, NUMERIC, fits

type Drivers = Mapping[str, Driver]  # by element type


def check_driver(driver: Driver, location: Location) -> tuple[Issue, ...]:
    """Every problem of meaning in ``driver``, pointing inside the file at ``location``."""
    issues = list(_duplicates(driver, location))
    issues += _parameter_issues(driver.config, ("config",), location)
    for index, action in enumerate(driver.actions):
        issues += _parameter_issues(action.parameters, ("actions", index, "parameters"), location)
    issues += _output_issues(driver, location)
    return tuple(issues)


def _at(location: Location, *steps: Step) -> Location:
    return replace(location, pointer=pointer(steps))


def _duplicates(driver: Driver, location: Location) -> Iterator[Issue]:
    code = CoreErrorCode.DRIVER_DUPLICATE_ACTION
    names = (action.name for action in driver.actions)
    yield from _once(names, code, "action", ("actions",), location)


def _once(
    names: Iterable[str], code: CoreErrorCode, param: str, steps: tuple[Step, ...], at: Location
) -> Iterator[Issue]:
    seen: set[str] = set()
    for index, name in enumerate(names):
        if name in seen:
            yield Issue(code, {param: name}, _at(at, *steps, index, "name"))
        seen.add(name)


def _parameter_issues(
    parameters: tuple[DriverParameter, ...], steps: tuple[Step, ...], location: Location
) -> Iterator[Issue]:
    code = CoreErrorCode.DRIVER_DUPLICATE_PARAMETER
    yield from _once((p.name for p in parameters), code, "parameter", steps, location)
    for index, parameter in enumerate(parameters):
        place = (*steps, index)
        yield from _limit_issues(parameter, place, location)
        yield from _choice_issues(parameter, place, location)
        yield from _default_issues(parameter, place, location)


def _limit_issues(
    parameter: DriverParameter, steps: tuple[Step, ...], location: Location
) -> Iterator[Issue]:
    """Limits only on numbers, both or neither, whole numbers for an integer, the minimum not
    above the maximum."""
    given = {"min": parameter.min, "max": parameter.max}
    numeric = parameter.type in NUMERIC
    for key, limit in given.items():
        field = {"field": field_name((*steps, key))}
        if limit is None:
            if numeric and any(other is not None for other in given.values()):
                yield Issue(CoreErrorCode.SCHEMA_MISSING_FIELD, field, _at(location, *steps))
        elif not numeric:
            yield Issue(CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, field, _at(location, *steps, key))
        elif parameter.type == "integer" and not limit.is_integer():
            code = CoreErrorCode.VALUE_EXPECTED_INTEGER
            yield Issue(code, field, _at(location, *steps, key))
    if parameter.min is not None and parameter.max is not None and parameter.min > parameter.max:
        params = {"parameter": parameter.name, **limits(parameter)}
        yield Issue(CoreErrorCode.DRIVER_LIMITS_INVALID, params, _at(location, *steps))


def _choice_issues(
    parameter: DriverParameter, steps: tuple[Step, ...], location: Location
) -> Iterator[Issue]:
    """Choices only on texts."""
    if parameter.choices and parameter.type != "text":
        field = {"field": field_name((*steps, "choices"))}
        yield Issue(CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, field, _at(location, *steps, "choices"))


def _default_issues(
    parameter: DriverParameter, steps: tuple[Step, ...], location: Location
) -> Iterator[Issue]:
    """A default of the parameter's type, within its limits and among its choices."""
    default = parameter.default
    if default is None:
        return
    place = _at(location, *steps, "default")
    allowed = not parameter.choices or default in parameter.choices
    if not fits(default, parameter.type):
        yield Issue(EXPECTED[parameter.type], {"field": field_name((*steps, "default"))}, place)
    elif not within(default, parameter) or not allowed:
        params = {"parameter": parameter.name}
        yield Issue(CoreErrorCode.DRIVER_DEFAULT_NOT_ALLOWED, params, place)


def _output_issues(driver: Driver, location: Location) -> Iterator[Issue]:
    """A driver with actions says where its elements rest and who wins a conflict; one without
    them (an input) says neither."""
    given = {"conflictPolicy": driver.conflict_policy, "safeState": driver.safe_state}
    for field, value in given.items():
        if driver.actions and value is None:
            yield Issue(CoreErrorCode.SCHEMA_MISSING_FIELD, {"field": field}, location)
        elif not driver.actions and value is not None:
            params = {"field": field}
            yield Issue(CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, params, _at(location, field))
    if driver.actions and driver.safe_state is not None:
        runs_without_arguments = {
            action.name
            for action in driver.actions
            if all(parameter.default is not None for parameter in action.parameters)
        }
        if driver.safe_state not in runs_without_arguments:
            params = {"action": driver.safe_state}
            code = CoreErrorCode.DRIVER_UNKNOWN_SAFE_STATE
            yield Issue(code, params, _at(location, "safeState"))
