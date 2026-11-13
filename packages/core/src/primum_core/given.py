"""Values given by name for the parameters a driver manifest declares.

A clip's arguments and an element's configuration are both that: ``check_given`` checks either
against the parameters, each caller with its own codes and its own place to report at.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace

from primum_core.errors import CoreErrorCode, Issue, Location, ParamValue
from primum_core.generated.model import DriverParameter, NamedValue
from primum_core.pointers import Step, field_name, pointer
from primum_core.values import EXPECTED, Value, fits

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
    elif not within(item.value, parameter):
        yield Issue(codes.out_of_range, {**params, **limits(parameter)}, place)
    elif parameter.choices and item.value not in parameter.choices:
        yield Issue(codes.not_allowed, {**params, "allowed": parameter.choices}, place)


def within(value: Value, parameter: DriverParameter) -> bool:
    """Whether a value of the parameter's type lies within its limits, if it has them."""
    if parameter.min is None or parameter.max is None or isinstance(value, bool | str):
        return True
    return parameter.min <= value <= parameter.max


def limits(parameter: DriverParameter) -> dict[str, float]:
    """The limits a parameter has, as messages show them: a whole number without its ``.0``."""
    limits = {"min": parameter.min, "max": parameter.max}
    return {
        key: int(limit) if float(limit).is_integer() else limit
        for key, limit in limits.items()
        if limit is not None
    }
