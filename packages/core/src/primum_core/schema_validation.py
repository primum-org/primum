"""Structural validation against the JSON Schemas in ``schemas/`` (decision 0008).

``fastjsonschema`` checks a document against its schema and reports every failure; each one
becomes an ``Issue`` with a code, params naming the field, and a JSON Pointer to it. The meaning
of a project (references, scopes, pins) is checked elsewhere, by ``core`` code.
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cache

import fastjsonschema

from primum_core.errors import CoreErrorCode, Issue, Location, ParamScalar, ParamValue
from primum_core.generated.schemas import SCHEMAS
from primum_core.json_values import is_array, is_object

VERSION_FIELD = "schemaVersion"

type Step = str | int
type Validator = Callable[[object], object]


@dataclass(frozen=True)
class _Failure:
    """One failure reported by fastjsonschema, with array indices as ints."""

    rule: str
    steps: tuple[Step, ...]
    value: object
    schema: Mapping[str, object]

    @property
    def expected(self) -> object:
        return self.schema.get(self.rule)


def validate(schema: str, document: object, location: Location) -> tuple[Issue, ...]:
    """Every structural problem of ``document`` against ``schemas/<schema>``, in order.

    ``location`` names the file; each issue points inside it.
    """
    try:
        _validator(schema)(document)
    except fastjsonschema.JsonSchemaValuesException as found:
        errors = found.errors
    except fastjsonschema.JsonSchemaValueException as found:
        errors = [found]
    else:
        return ()
    return tuple(
        issue for error in errors for issue in _issues(_failure(error, document), location)
    )


@cache
def _validator(schema: str) -> Validator:
    # Every error, not only the first; and never fill in defaults: the document is not changed.
    return fastjsonschema.compile(
        SCHEMAS[schema],
        handlers={"": _referenced_schema},
        use_default=False,
        fast_fail=False,
    )


def _referenced_schema(uri: str) -> Mapping[str, object]:
    """Schemas refer to each other by file name (``common.schema.json#/$defs/id``)."""
    return SCHEMAS[uri]


def _failure(error: fastjsonschema.JsonSchemaValueException, document: object) -> _Failure:
    return _Failure(
        rule=error.rule,
        steps=_typed_steps(error.path[1:], document),  # the first step is the document itself
        value=error.value,
        schema=error.definition,
    )


def _typed_steps(raw: Sequence[str], document: object) -> tuple[Step, ...]:
    """Array indices as ints: fastjsonschema reports ``tags[0]`` as ``tags``, ``0``."""
    steps: list[Step] = []
    current = document
    for step in raw:
        if is_array(current) and step.isdecimal():
            index = int(step)
            steps.append(index)
            current: object = current[index] if index < len(current) else None
        else:
            steps.append(step)
            current = current.get(step) if is_object(current) else None
    return tuple(steps)


def _issues(failure: _Failure, location: Location) -> Iterator[Issue]:
    steps = failure.steps
    match failure.rule:
        case "required":
            present = failure.value if is_object(failure.value) else {}
            for name in _names(failure.expected):
                if name not in present:
                    yield _issue(CoreErrorCode.SCHEMA_MISSING_FIELD, (*steps, name), location)
        case "additionalProperties":
            known = set(_names(failure.schema.get("properties")))
            extra = failure.value if is_object(failure.value) else {}
            for name in sorted(key for key in extra if key not in known):
                yield _issue(CoreErrorCode.SCHEMA_UNKNOWN_FIELD, (*steps, name), location)
        case "type" if not steps:
            yield Issue(CoreErrorCode.FILE_NOT_AN_OBJECT, location=location)
        case "const" if steps == (VERSION_FIELD,) and _is_int(failure.value):
            yield Issue(
                CoreErrorCode.SCHEMA_UNSUPPORTED_VERSION,
                {"version": _scalar(failure.value), "supported": _scalar(failure.expected)},
                replace(location, pointer=_pointer(steps)),
            )
        case rule:
            code, extra_params = _code_for(rule, failure.expected)
            yield _issue(code, steps, location, **extra_params)


def _code_for(rule: str, expected: object) -> tuple[CoreErrorCode, dict[str, ParamValue]]:
    """The code of a failure that concerns one value, and the params it adds to ``field``."""
    match rule:
        case "type":
            return CoreErrorCode.SCHEMA_WRONG_TYPE, {"expected": _scalar(expected)}
        case "const":
            return CoreErrorCode.SCHEMA_NOT_ALLOWED, {"allowed": (_scalar(expected),)}
        case "enum":
            return CoreErrorCode.SCHEMA_NOT_ALLOWED, {"allowed": _scalars(expected)}
        case "format":
            return CoreErrorCode.SCHEMA_INVALID_FORMAT, {"format": _scalar(expected)}
        case "minLength":
            return CoreErrorCode.SCHEMA_TOO_SHORT, {"min": _scalar(expected)}
        case "maxLength":
            return CoreErrorCode.SCHEMA_TOO_LONG, {"max": _scalar(expected)}
        case "minItems":
            return CoreErrorCode.SCHEMA_TOO_FEW_ITEMS, {"min": _scalar(expected)}
        case "maxItems":
            return CoreErrorCode.SCHEMA_TOO_MANY_ITEMS, {"max": _scalar(expected)}
        case "minimum":
            return CoreErrorCode.SCHEMA_BELOW_MINIMUM, {"minimum": _scalar(expected)}
        case "maximum":
            return CoreErrorCode.SCHEMA_ABOVE_MAXIMUM, {"maximum": _scalar(expected)}
        case "uniqueItems":
            return CoreErrorCode.SCHEMA_DUPLICATE_ITEMS, {}
        case _:  # pattern, and any rule the schemas may use later without a code of its own
            return CoreErrorCode.SCHEMA_INVALID_VALUE, {}


def _issue(
    code: CoreErrorCode,
    steps: tuple[Step, ...],
    location: Location,
    **params: ParamValue,
) -> Issue:
    """An issue about the field at ``steps``; it points there, or at its object if missing."""
    pointer_steps = steps[:-1] if code is CoreErrorCode.SCHEMA_MISSING_FIELD else steps
    return Issue(
        code,
        {"field": _field(steps), **params},
        replace(location, pointer=_pointer(pointer_steps)),
    )


def _field(steps: tuple[Step, ...]) -> str:
    """How a person reads a field: ``outputs[2].name``."""
    text = ""
    for step in steps:
        text += f"[{step}]" if isinstance(step, int) else f".{step}" if text else step
    return text


def _pointer(steps: tuple[Step, ...]) -> str:
    """A JSON Pointer (RFC 6901): ``/outputs/2/name``."""
    return "".join(f"/{str(step).replace('~', '~0').replace('/', '~1')}" for step in steps)


def _names(value: object) -> list[str]:
    """The keys of a JSON object or the items of a JSON array, as names."""
    if is_object(value):
        return list(value)
    if is_array(value):
        return [str(item) for item in value]
    return []


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _scalar(value: object) -> ParamScalar:
    return value if isinstance(value, str | int | float | bool) else str(value)


def _scalars(value: object) -> tuple[ParamScalar, ...]:
    return tuple(_scalar(item) for item in value) if is_array(value) else (_scalar(value),)
