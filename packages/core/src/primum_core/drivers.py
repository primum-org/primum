"""Driver manifests: what one means beyond its schema, and what a project gives it by name.

A manifest (``drivers/<elementType>.json``) describes a driver as data: the actions a clip may
ask of its elements, each with its parameters, and the options an element of its type takes
in a ``.hw`` file (its configuration). Its schema checks the shape; ``check_driver`` checks
what the shape cannot say. Callers read the file and use ``primum_core.formats.read_driver``,
which runs it, and pass the manifests, by element type, to the workspace loader.

A clip's arguments and an element's configuration are both values given by name for the parameters
a manifest declares: ``check_given`` checks either against them.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace

from primum_core.errors import CoreErrorCode, Issue, Location, ParamValue
from primum_core.generated.model import Driver, DriverParameter, NamedValue
from primum_core.pointers import Step, field_name, pointer
from primum_core.values import EXPECTED, NUMERIC, Value, fits

type Drivers = Mapping[str, Driver]  # by element type
type _Params = dict[str, ParamValue]


@dataclass(frozen=True)
class Where:
    """Where values are given by name: the clip or the element (``steps`` to it in the file at
    ``location``) and its list of them (``field``). Without ``steps`` everything is reported
    at ``location`` as it is: the block through which a component's clip came."""

    location: Location
    steps: tuple[Step, ...] | None
    field: str

    def at(self, *steps: Step) -> Location:
        """A place inside the clip or the element."""
        if self.steps is None:
            return self.location
        return replace(self.location, pointer=pointer((*self.steps, *steps)))

    def value_field(self, index: int, name: str) -> str:
        """How a person reads the value of one of them."""
        if self.steps is None:
            return name
        return field_name((*self.steps, self.field, index, "value"))


@dataclass(frozen=True)
class GivenCodes:
    """The codes for values given by name, and the param that carries the name."""

    key: str
    unknown: CoreErrorCode
    duplicate: CoreErrorCode
    missing: CoreErrorCode
    out_of_range: CoreErrorCode
    not_allowed: CoreErrorCode


def check_given(
    given: tuple[NamedValue, ...],
    parameters: tuple[DriverParameter, ...],
    codes: GivenCodes,
    context: Mapping[str, ParamValue],
    where: Where,
) -> Iterator[Issue]:
    """What is wrong with ``given`` for ``parameters``: a name they do not declare or given
    twice, a value of another type, outside the limits or not one of the choices, and a
    parameter without a default that is not given. ``context`` goes in every issue's params.
    """
    declared = {parameter.name: parameter for parameter in parameters}
    seen: set[str] = set()
    for index, item in enumerate(given):
        place = where.at(where.field, index)
        params: _Params = {**context, codes.key: item.name}
        parameter = declared.get(item.name)
        if parameter is None:
            yield Issue(codes.unknown, params, place)
        elif item.name in seen:
            yield Issue(codes.duplicate, params, place)
        else:
            seen.add(item.name)
            yield from _value_issues(item, parameter, codes, params, where, index)
    for parameter in parameters:
        if parameter.default is None and parameter.name not in seen:
            yield Issue(codes.missing, {**context, codes.key: parameter.name}, where.at())


def _value_issues(
    item: NamedValue,
    parameter: DriverParameter,
    codes: GivenCodes,
    params: _Params,
    where: Where,
    index: int,
) -> Iterator[Issue]:
    place = where.at(where.field, index, "value")
    if not fits(item.value, parameter.type):
        field = {"field": where.value_field(index, item.name)}
        yield Issue(EXPECTED[parameter.type], field, place)
    elif not _within(item.value, parameter):
        limits = {"min": _tidy(parameter.min), "max": _tidy(parameter.max)}
        yield Issue(codes.out_of_range, {**params, **limits}, place)
    elif parameter.choices and item.value not in parameter.choices:
        yield Issue(codes.not_allowed, {**params, "allowed": parameter.choices}, place)


def _within(value: Value, parameter: DriverParameter) -> bool:
    """Whether a value of the parameter's type lies within its limits, if it has them."""
    if parameter.min is None or parameter.max is None or isinstance(value, bool | str):
        return True
    return parameter.min <= value <= parameter.max


def _tidy(number: float | None) -> float:
    """A whole number without its ``.0``, as messages show it."""
    if number is None:
        return 0
    return int(number) if float(number).is_integer() else number


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
        yield from _coherence_issues(parameter, (*steps, index), location)


def _coherence_issues(
    parameter: DriverParameter, steps: tuple[Step, ...], location: Location
) -> Iterator[Issue]:
    """Limits only on numbers and in pairs, the right way round; choices only on texts; a
    default of the parameter's type, within its limits or among its choices."""
    name = {"parameter": parameter.name}
    limits = {"min": parameter.min, "max": parameter.max}
    numeric = parameter.type in NUMERIC
    for key, limit in limits.items():
        field = {"field": field_name((*steps, key))}
        if limit is not None and not numeric:
            yield Issue(CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, field, _at(location, *steps, key))
        elif limit is None and numeric and any(other is not None for other in limits.values()):
            yield Issue(CoreErrorCode.SCHEMA_MISSING_FIELD, field, _at(location, *steps))
    if parameter.choices and parameter.type != "text":
        field = {"field": field_name((*steps, "choices"))}
        yield Issue(CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, field, _at(location, *steps, "choices"))
    if parameter.min is not None and parameter.max is not None and parameter.min > parameter.max:
        params = {**name, "min": _tidy(parameter.min), "max": _tidy(parameter.max)}
        yield Issue(CoreErrorCode.DRIVER_LIMITS_INVALID, params, _at(location, *steps))
    default = parameter.default
    if default is None:
        return
    place = _at(location, *steps, "default")
    if not fits(default, parameter.type):
        yield Issue(EXPECTED[parameter.type], {"field": field_name((*steps, "default"))}, place)
    elif not _within(default, parameter) or (
        parameter.choices and default not in parameter.choices
    ):
        yield Issue(CoreErrorCode.DRIVER_DEFAULT_NOT_ALLOWED, name, place)


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
