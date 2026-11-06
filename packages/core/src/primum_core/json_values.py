"""Typed access to JSON values that already passed schema validation.

The generated model (``primum_core.generated.model``) builds its dataclasses with the ``as_*``
functions. A failure in them means a schema and the generated model disagree: a bug in Primum,
never a problem in a user's file, so they raise instead of reporting an ``Issue``.
"""

from collections.abc import Mapping, Sequence
from typing import TypeIs
from uuid import UUID

type JsonObject = Mapping[str, object]
type JsonScalar = str | int | float | bool


def is_object(value: object) -> TypeIs[dict[str, object]]:
    """A decoded JSON object (``json.loads`` gives ``dict`` with string keys)."""
    return isinstance(value, dict)


def is_array(value: object) -> TypeIs[list[object]]:
    return isinstance(value, list)


def _mismatch(value: object, expected: str) -> TypeError:
    found = type(value).__name__
    return TypeError(f"expected {expected}, got {found}: the schema and the model disagree")


def as_object(value: object) -> JsonObject:
    if not is_object(value):
        raise _mismatch(value, "an object")
    return value


def as_list(value: object) -> list[object]:
    if not is_array(value):
        raise _mismatch(value, "an array")
    return value


def as_str(value: object) -> str:
    if not isinstance(value, str):
        raise _mismatch(value, "a string")
    return value


def as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _mismatch(value, "an integer")
    return value


def as_float(value: object) -> float:
    """A JSON number: ``2`` and ``2.0`` are the same number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _mismatch(value, "a number")
    return float(value)


def as_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise _mismatch(value, "a boolean")
    return value


def as_scalar(value: object) -> JsonScalar:
    """A text, a number or a boolean: a value whose schema allows several scalar types."""
    if not isinstance(value, str | int | float | bool):
        raise _mismatch(value, "a text, a number or a boolean")
    return value


def as_uuid(value: object) -> UUID:
    return UUID(as_str(value))


def as_choice[T: str | int](value: object, choices: Sequence[T]) -> T:
    """One of the values of an ``enum``, typed as the ``Literal`` of ``choices``.

    ``choices`` is a constant typed ``tuple[Literal[...], ...]``: the type checker then knows
    the result is one of them.
    """
    for choice in choices:
        if value == choice and type(value) is type(choice):
            return choice
    raise _mismatch(value, f"one of {tuple(choices)}")
