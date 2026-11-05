"""Read Primum files: bytes in, a typed value or the issues that prevent it out.

``core`` reads no files: the caller passes the content it read, and the path where it found it
(for display). Each file goes through three steps, and stops at the first that fails:

1. text and JSON: UTF-8 (a byte order mark is accepted), valid JSON, no repeated keys, and
   numbers as JSON means them (``2.0`` is the integer ``2``);
2. structure: the file's schema in ``schemas/``, every problem reported;
3. the generated, immutable dataclass of the format;
4. meaning, for formats that have rules a schema cannot express (board profiles).
"""

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID

from primum_core.boards import check_board_profile
from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.generated.model import BoardProfile, Project, parse_board_profile, parse_project
from primum_core.json_values import JsonObject, as_object, is_object
from primum_core.schema_validation import validate

ID_FIELD = "id"

type Check[T] = Callable[[T, Location], tuple[Issue, ...]]


@dataclass(frozen=True)
class Parsed[T]:
    """What reading a file gave: the value, or ``None`` and the issues that prevented it."""

    value: T | None
    issues: tuple[Issue, ...] = ()


class _NotStandardJson:
    """``NaN``, ``Infinity`` and numbers too large for a float: Python's json accepts them, JSON
    has no such values.

    The value is kept in the document as this marker, so the schema reports it, with its field,
    as a value of the wrong type.
    """


class _DuplicateKeyError(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def read_manifest(path: PurePosixPath, content: bytes) -> Parsed[Project]:
    """Read a project's manifest (``project.json``)."""
    return _read(path, content, "project.schema.json", parse_project)


def read_board_profile(path: PurePosixPath, content: bytes) -> Parsed[BoardProfile]:
    """Read a board profile (``boards/<model>.json``), its meaning checked too."""
    return _read(
        path, content, "board-profile.schema.json", parse_board_profile, check_board_profile
    )


def _read[T](
    path: PurePosixPath,
    content: bytes,
    schema: str,
    parse: Callable[[JsonObject], T],
    check: Check[T] | None = None,
) -> Parsed[T]:
    location = Location(path)
    document = _decode(content, location)
    if isinstance(document, Issue):
        return Parsed(None, (document,))
    location = Location(path, file_id=_file_id(document))
    issues = validate(schema, document, location)
    if issues:
        return Parsed(None, issues)
    value = parse(as_object(document))
    issues = check(value, location) if check else ()
    return Parsed(None, issues) if issues else Parsed(value)


def _decode(content: bytes, location: Location) -> object:
    """The JSON document in ``content``, or the ``Issue`` that prevents reading it."""
    try:
        text = content.decode("utf-8-sig")  # editors on Windows may add a byte order mark
    except UnicodeDecodeError:
        return Issue(CoreErrorCode.FILE_NOT_UTF8, location=location)
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_without_repeated_keys,
            parse_constant=lambda _: _NotStandardJson(),
            parse_float=_number,
        )
    except _DuplicateKeyError as repeated:
        return Issue(CoreErrorCode.FILE_DUPLICATE_KEY, {"key": repeated.key}, location)
    except json.JSONDecodeError as invalid:
        return Issue(
            CoreErrorCode.FILE_INVALID_JSON,
            {"line": invalid.lineno, "column": invalid.colno},
            location,
        )


def _number(text: str) -> object:
    """A JSON number with a fraction or an exponent (``2.0``, ``5e2``, ``0.5``).

    JSON Schema counts ``2.0`` as an integer, so the schema accepts it where an integer goes;
    it becomes the int ``2`` here, so the model gets the type the schema promised.
    """
    value = float(text)
    if not math.isfinite(value):
        return _NotStandardJson()
    return int(value) if value.is_integer() else value


def _object_without_repeated_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """JSON allows a key twice and keeps the last one, which hides mistakes: refuse it."""
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise _DuplicateKeyError(key)
        document[key] = value
    return document


def _file_id(document: object) -> UUID | None:
    """The file's id, if it has a valid one, so issues can point at the file by id."""
    if not is_object(document):
        return None
    value = document.get(ID_FIELD)
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None
