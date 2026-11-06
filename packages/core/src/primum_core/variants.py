"""Fields that depend on the case: what a schema without variants cannot say.

Some objects take different fields depending on one of them: an element on a GPIO needs a
``pin`` while an I2C device needs a ``bus`` and an ``address``; an event from an element needs
the element; an automation action that starts a sequence names it; only a numeric variable has
limits. A missing field is ``schema.missing_field`` and a field that does not apply to the case
is ``schema.unexpected_field``, both pointing at it.

Constants and variables also carry a value of their declared type, and a variable's initial
value lies within its limits (``value.expected_*``, ``variable.*``).
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace

from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.generated.model import (
    Automation,
    AutomationAction,
    Element,
    Event,
    Hardware,
    Variable,
    Variables,
)
from primum_core.pointers import Step, field_name, pointer
from primum_core.references import LocatedContent
from primum_core.values import NUMERIC, check_value


@dataclass(frozen=True)
class _Case:
    """The fields one case needs, and the ones it must not have."""

    required: frozenset[str] = frozenset()
    unexpected: frozenset[str] = frozenset()


def _case(required: str = "", unexpected: str = "") -> _Case:
    return _Case(frozenset(required.split()), frozenset(unexpected.split()))


GPIO_ELEMENT = _case(required="pin", unexpected="bus address")
ELEMENT_CASES: Mapping[str, _Case] = {
    "digital_output": GPIO_ELEMENT,
    "digital_input": GPIO_ELEMENT,
    "pwm_output": GPIO_ELEMENT,
    "i2c_device": _case(required="bus address", unexpected="pin activeLow"),
}
EVENT_CASES: Mapping[str, _Case] = {
    "element": _case(required="element trigger"),
    "ui": _case(unexpected="element trigger"),
    "api": _case(unexpected="element trigger"),
}
ACTION_CASES: Mapping[str, _Case] = {
    "start_sequence": _case(required="sequence", unexpected="variable value"),
    "stop_sequence": _case(required="sequence", unexpected="variable value"),
    "set_variable": _case(required="variable value", unexpected="sequence"),
    # value is the amount, 1 when absent.
    "increment_variable": _case(required="variable", unexpected="sequence"),
}


def check_variants(file: LocatedContent) -> tuple[Issue, ...]:
    """Every field missing for its case, or present where the case does not use it."""
    content = file.content
    match content:
        case Hardware():
            return tuple(
                issue
                for index, element in enumerate(content.elements)
                for issue in _check(
                    ELEMENT_CASES[element.type],
                    _element_fields(element),
                    ("elements", index),
                    file.location,
                )
            )
        case Event():
            return tuple(
                _check(EVENT_CASES[content.source], _event_fields(content), (), file.location)
            )
        case Automation():
            return tuple(
                issue
                for index, action in enumerate(content.do)
                for issue in _check(
                    ACTION_CASES[action.action],
                    _action_fields(action),
                    ("do", index),
                    file.location,
                )
            )
        case Variables():
            return tuple(_variables_issues(content, file.location))
        case _:
            return ()


def _variables_issues(content: Variables, location: Location) -> Iterator[Issue]:
    for index, constant in enumerate(content.constants):
        steps: tuple[Step, ...] = ("constants", index, "value")
        if issue := check_value(constant.value, constant.type, steps, location):
            yield issue
    for index, variable in enumerate(content.variables):
        yield from _variable_issues(variable, ("variables", index), location)


def _variable_issues(
    variable: Variable, steps: tuple[Step, ...], location: Location
) -> Iterator[Issue]:
    at = replace(location, pointer=pointer(steps))
    if variable.type not in NUMERIC:
        limits = {"min": variable.min is not None, "max": variable.max is not None}
        yield from _check(_case(unexpected="min max"), limits, steps, location)
    if issue := check_value(variable.initial, variable.type, (*steps, "initial"), location):
        yield issue
        return
    if variable.min is not None and variable.max is not None and variable.min > variable.max:
        params = {"name": variable.name, "min": variable.min, "max": variable.max}
        yield Issue(CoreErrorCode.VARIABLE_LIMITS_INVALID, params, at)
        return
    initial = variable.initial
    if isinstance(initial, int | float) and not isinstance(initial, bool):
        below = variable.min is not None and initial < variable.min
        above = variable.max is not None and initial > variable.max
        if below or above:
            params = {"name": variable.name, "initial": initial}
            yield Issue(CoreErrorCode.VARIABLE_INITIAL_OUT_OF_RANGE, params, at)


def _element_fields(element: Element) -> Mapping[str, bool]:
    return {
        "pin": element.pin is not None,
        "bus": element.bus is not None,
        "address": element.address is not None,
        # A default of false says nothing: only an active-low I2C device is a mistake.
        "activeLow": element.active_low,
    }


def _event_fields(event: Event) -> Mapping[str, bool]:
    return {"element": event.element is not None, "trigger": event.trigger is not None}


def _action_fields(action: AutomationAction) -> Mapping[str, bool]:
    return {
        "sequence": action.sequence is not None,
        "variable": action.variable is not None,
        "value": action.value is not None,
    }


def _check(
    case: _Case, present: Mapping[str, bool], steps: tuple[Step, ...], location: Location
) -> Iterator[Issue]:
    for name in sorted(case.required):
        if not present[name]:
            yield Issue(
                CoreErrorCode.SCHEMA_MISSING_FIELD,
                {"field": field_name((*steps, name))},
                replace(location, pointer=pointer(steps)),
            )
    for name in sorted(case.unexpected):
        if present[name]:
            yield Issue(
                CoreErrorCode.SCHEMA_UNEXPECTED_FIELD,
                {"field": field_name((*steps, name))},
                replace(location, pointer=pointer((*steps, name))),
            )
