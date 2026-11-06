"""Fields that depend on the case: what a schema without variants cannot say.

Some objects take different fields depending on one of them: an element on a GPIO needs a
``pin`` while an I2C device needs a ``bus`` and an ``address``; an event from an element needs
the element; an automation action that starts a sequence names it. A missing field is
``schema.missing_field`` and a field that does not apply to the case is
``schema.unexpected_field``, both pointing at it.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace

from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.generated.model import Automation, AutomationAction, Element, Event, Hardware
from primum_core.pointers import Step, field_name, pointer
from primum_core.references import LocatedContent


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
        case _:
            return ()


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
