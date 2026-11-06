"""Values and the types they are declared with (``number``, ``integer``, ``boolean``, ``text``).

A constant's value, a variable's initial value, the value an automation sets and the value given
to a component's parameter must all be of the declared type. A value of another type is
reported with one code per expected type, so messages never quote type names.
"""

from dataclasses import replace
from typing import Literal

from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.pointers import Step, field_name, pointer

type ValueType = Literal["number", "integer", "boolean", "text"]
type Value = float | bool | str

NUMERIC: frozenset[str] = frozenset({"number", "integer"})
EXPECTED: dict[str, CoreErrorCode] = {
    "number": CoreErrorCode.VALUE_EXPECTED_NUMBER,
    "integer": CoreErrorCode.VALUE_EXPECTED_INTEGER,
    "boolean": CoreErrorCode.VALUE_EXPECTED_BOOLEAN,
    "text": CoreErrorCode.VALUE_EXPECTED_TEXT,
}


def fits(value: Value, value_type: str) -> bool:
    """Whether ``value`` is of ``value_type``. A boolean is never a number; ``2`` is a number."""
    match value_type:
        case "boolean":
            return isinstance(value, bool)
        case "text":
            return isinstance(value, str)
        case "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        case _:
            return isinstance(value, int | float) and not isinstance(value, bool)


def check_value(
    value: Value, value_type: str, steps: tuple[Step, ...], location: Location
) -> Issue | None:
    """The issue for a value that is not of ``value_type``, pointing at the value."""
    if fits(value, value_type):
        return None
    return Issue(
        EXPECTED[value_type],
        {"field": field_name(steps)},
        replace(location, pointer=pointer(steps)),
    )
