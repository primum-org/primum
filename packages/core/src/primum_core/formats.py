"""Read Primum files: bytes in, a typed value or the issues that prevent it out.

``core`` reads no files: the caller passes the content it read, and the path where it found it
(for display). Each file goes through three steps, and stops at the first that fails:

1. text and JSON: UTF-8 (a byte order mark is accepted), valid JSON, no repeated keys, and
   numbers as JSON means them (``2.0`` is the integer ``2``);
2. structure: the file's schema in ``schemas/``, every problem reported;
3. the generated, immutable dataclass of the format;
4. meaning, for formats that have rules a schema cannot express (board profiles, driver
   manifests).
"""

import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID

from primum_core.boards import check_board_profile
from primum_core.drivers import check_driver
from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.generated.model import (
    Automation,
    BoardProfile,
    Driver,
    Event,
    Hardware,
    Project,
    Schedule,
    Sequence,
    Variables,
    parse_automation,
    parse_board_profile,
    parse_driver,
    parse_event,
    parse_hardware,
    parse_project,
    parse_schedule,
    parse_sequence,
    parse_variables,
)
from primum_core.json_values import JsonObject, as_object, is_array, is_object
from primum_core.schema_validation import validate

ID_FIELD = "id"
HALF_A_CHARACTER = re.compile("[\ud800-\udfff]")

type Check[T] = Callable[[T, Location], tuple[Issue, ...]]
# The content of a project file other than the manifest, by its extension.
type ProjectFileContent = Hardware | Variables | Sequence | Event | Schedule | Automation

PROJECT_FILE_FORMATS: Mapping[str, tuple[str, Callable[[JsonObject], ProjectFileContent]]] = {
    ".hw": ("hardware.schema.json", parse_hardware),
    ".vars": ("variables.schema.json", parse_variables),
    ".sec": ("sequence.schema.json", parse_sequence),
    ".evt": ("event.schema.json", parse_event),
    ".sched": ("schedule.schema.json", parse_schedule),
    ".auto": ("automation.schema.json", parse_automation),
}


@dataclass(frozen=True)
class Parsed[T]:
    """What reading gave: the value, or ``None`` if an error prevented it, and the issues.

    Warnings do not prevent the value: a value may come with issues, all of them warnings.
    """

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


def read_project_file(path: PurePosixPath, content: bytes) -> Parsed[ProjectFileContent]:
    """Read a project file of a type in ``PROJECT_FILE_FORMATS``, chosen by its extension."""
    schema, parse = PROJECT_FILE_FORMATS[path.suffix.lower()]
    return _read(path, content, schema, parse)


def read_board_profile(path: PurePosixPath, content: bytes) -> Parsed[BoardProfile]:
    """Read a board profile (``boards/<model>.json``), its meaning checked too."""
    return _read(
        path, content, "board-profile.schema.json", parse_board_profile, check_board_profile
    )


def read_driver(path: PurePosixPath, content: bytes) -> Parsed[Driver]:
    """Read a driver manifest (``drivers/<elementType>.json``), its meaning checked too."""
    return _read(path, content, "driver.schema.json", parse_driver, check_driver)


def read_drivers(files: Mapping[PurePosixPath, bytes]) -> Parsed[Mapping[str, Driver]]:
    """Read every driver manifest of ``drivers/`` (path → content) into what the workspace
    loader takes: each by its own element type, whatever its file is called. They come back
    when all of them read and no two are of one type."""
    drivers: dict[str, Driver] = {}
    issues: list[Issue] = []
    for path in sorted(files):
        parsed = read_driver(path, files[path])
        issues += parsed.issues
        if parsed.value is None:
            continue
        element_type = parsed.value.element_type
        if element_type in drivers:
            location = Location(path, "/elementType", parsed.value.id)
            code = CoreErrorCode.DRIVER_DUPLICATE_TYPE
            issues.append(Issue(code, {"type": element_type}, location))
        drivers[element_type] = parsed.value
    return Parsed(None, tuple(issues)) if issues else Parsed(drivers)


def _read[T](
    path: PurePosixPath,
    content: bytes,
    schema: str,
    parse: Callable[[JsonObject], T],
    check: Check[T] | None = None,
) -> Parsed[T]:
    location = Location(path)
    document = decode(content, location)
    if isinstance(document, Issue):
        return Parsed(None, (document,))
    location = Location(path, file_id=_file_id(document))
    issues = validate(schema, document, location)
    if issues:
        return Parsed(None, issues)
    value = parse(as_object(document))
    issues = check(value, location) if check else ()
    return Parsed(None, issues) if issues else Parsed(value)


def decode(content: bytes, location: Location) -> object:
    """The JSON document in ``content``, or the ``Issue`` that prevents reading it: UTF-8, no
    repeated keys, numbers as JSON means them, and only text that can be written again."""
    document = _loaded(content, location)
    if not isinstance(document, Issue) and _has_half_a_character(document):
        return Issue(CoreErrorCode.FILE_INVALID_TEXT, location=location)
    return document


def _has_half_a_character(value: object) -> bool:
    """Whether a text anywhere in ``value``, a key included, has a surrogate without its pair.

    JSON lets one be written (``"\\ud83d"``) and Python reads it, but it is no character:
    nothing can write it as UTF-8, so it would raise wherever the text is next encoded (the
    hash of a package). A pair written as two escapes is read as its one character."""
    if isinstance(value, str):
        return HALF_A_CHARACTER.search(value) is not None
    if is_object(value):
        return any(
            _has_half_a_character(key) or _has_half_a_character(item) for key, item in value.items()
        )
    return is_array(value) and any(_has_half_a_character(item) for item in value)


def _loaded(content: bytes, location: Location) -> object:
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
            parse_int=_integer,
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


def _integer(text: str) -> object:
    """A JSON integer. One that no float can hold (hundreds of digits) is no number the model
    can carry: reported like the other numbers JSON does not have, not raised."""
    try:
        value = int(text)
        float(value)
    except (ValueError, OverflowError):  # ValueError: more digits than Python converts
        return _NotStandardJson()
    return value


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
