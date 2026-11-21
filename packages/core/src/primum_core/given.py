"""Values given by name for the parameters a driver manifest declares.

A clip's arguments and an element's configuration are both that: ``check_given`` checks either
against the parameters, each caller with its own codes and its own place to report at. A value
is written, or comes from somewhere (``primum_core.sources``): a constant counts as written;
of a variable only its type and its limits are known, and they must fit the parameter's, since
nothing checks the value again before it reaches the driver; of a component's parameter that
nothing has given yet, only its type.
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from uuid import UUID

from primum_core.errors import CoreErrorCode, Issue, Location, ParamValue
from primum_core.generated.model import DriverParameter
from primum_core.pointers import Step, field_name, pointer
from primum_core.values import EXPECTED, NUMERIC, Value, fits

type _Params = dict[str, ParamValue]


@dataclass(frozen=True)
class Fixed:
    """A value known when the project is compiled: written, or a constant's."""

    value: Value


@dataclass(frozen=True)
class FromVariable:
    """The value a variable has while running: only its type and its limits are known."""

    id: UUID
    name: str
    value_type: str
    min: float | None
    max: float | None


@dataclass(frozen=True)
class Unbound:
    """A value parameter of a component, seen where nothing has given it a value yet."""

    name: str
    value_type: str


type Source = Fixed | FromVariable | Unbound


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

    def value_field(self, index: int, name: str, field: str) -> str:
        """How a person reads the value of one of them."""
        if self.steps is None:
            return name
        return field_name((*self.steps, self.field, index, field))


@dataclass(frozen=True)
class Given:
    """A value given by name: where it comes from (``None``: a name that stands for nothing,
    reported elsewhere) and the field it is written in. ``typed`` says its type was already
    checked on the way here (a component's parameter, given by a block): one of another type
    is reported there, and not again."""

    name: str
    source: Source | None
    field: str = "value"
    typed: bool = False


@dataclass(frozen=True)
class GivenCodes:
    """The codes for values given by name, and the param that carries the name."""

    key: str
    unknown: CoreErrorCode
    duplicate: CoreErrorCode
    missing: CoreErrorCode
    out_of_range: CoreErrorCode
    not_allowed: CoreErrorCode
    # For values that may come from a variable (a clip's arguments).
    variable_unlimited: CoreErrorCode | None = None
    variable_choices: CoreErrorCode | None = None


def check_given(
    given: Sequence[Given],
    parameters: tuple[DriverParameter, ...],
    codes: GivenCodes,
    context: Mapping[str, ParamValue],
    where: Where,
    only: frozenset[int] | None = None,
) -> Iterator[Issue]:
    """What is wrong with ``given`` for ``parameters``: a name they do not declare or given
    twice, a value of another type, outside the limits or not one of the choices, and a
    parameter that must be given (no default, not optional) and is not. ``context`` goes in
    every issue's params. With ``only``, just the values of those of ``given``, by index: what
    became known about them here, the rest having been checked before.
    """
    declared = {parameter.name: parameter for parameter in parameters}
    seen: set[str] = set()
    for index, item in enumerate(given):
        place = where.at(where.field, index)
        params: _Params = {**context, codes.key: item.name}
        parameter = declared.get(item.name)
        if parameter is None or item.name in seen:
            if only is None:
                code = codes.unknown if parameter is None else codes.duplicate
                yield Issue(code, params, place)
            continue
        seen.add(item.name)
        if only is None or index in only:
            yield from _value_issues(item, parameter, codes, params, where, index)
    if only is not None:
        return
    for parameter in parameters:
        if needs_value(parameter) and parameter.name not in seen:
            yield Issue(codes.missing, {**context, codes.key: parameter.name}, where.at())


def _value_issues(
    item: Given,
    parameter: DriverParameter,
    codes: GivenCodes,
    params: _Params,
    where: Where,
    index: int,
) -> Iterator[Issue]:
    place = where.at(where.field, index, item.field)
    wrong_type = Issue(
        EXPECTED[parameter.type],
        {"field": where.value_field(index, item.name, item.field)},
        place,
    )
    match item.source:
        case None:
            return
        case Fixed(value):
            if not fits(value, parameter.type):
                if not item.typed:
                    yield wrong_type
            elif not within(value, parameter):
                yield Issue(codes.out_of_range, {**params, **limits(parameter)}, place)
            elif parameter.choices and value not in parameter.choices:
                yield Issue(codes.not_allowed, {**params, "allowed": parameter.choices}, place)
        case Unbound(_, value_type):
            if not type_fits(value_type, parameter.type):
                yield wrong_type
        case FromVariable(_, name, value_type, low, high):
            named: _Params = {**params, "name": name}
            if not type_fits(value_type, parameter.type):
                if not item.typed:
                    yield wrong_type
            elif codes.variable_unlimited and not limits_within(low, high, parameter):
                yield Issue(codes.variable_unlimited, {**named, **limits(parameter)}, place)
            elif codes.variable_choices and parameter.choices:
                yield Issue(codes.variable_choices, {**named, "allowed": parameter.choices}, place)


def type_fits(value_type: str, wanted: str) -> bool:
    """Whether every value of ``value_type`` is one of ``wanted``: a whole number is a number."""
    return value_type == wanted or (value_type == "integer" and wanted in NUMERIC)


def limits_within(low: float | None, high: float | None, parameter: DriverParameter) -> bool:
    """Whether a variable limited from ``low`` to ``high`` holds only what the parameter takes:
    on each side the parameter limits, the variable is limited too, and no further out."""
    if parameter.min is not None and (low is None or low < parameter.min):
        return False
    return parameter.max is None or (high is not None and high <= parameter.max)


def needs_value(parameter: DriverParameter) -> bool:
    """Whether the parameter must be given: it has no default and may not be left out."""
    return parameter.default is None and not parameter.optional


def within(value: Value, parameter: DriverParameter) -> bool:
    """Whether a value of the parameter's type lies within the limits it has."""
    if isinstance(value, bool | str):
        return True
    below = parameter.min is not None and value < parameter.min
    return not below and not (parameter.max is not None and value > parameter.max)


def limits(parameter: DriverParameter) -> dict[str, float]:
    """The limits a parameter has, as messages show them: a whole number without its ``.0``."""
    limits = {"min": parameter.min, "max": parameter.max}
    return {key: shown(limit) for key, limit in limits.items() if limit is not None}


def shown(limit: float) -> float:
    """A limit as messages show it: a whole number without its ``.0``."""
    return int(limit) if float(limit).is_integer() else limit
