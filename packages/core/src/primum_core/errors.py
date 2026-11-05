"""Problems that ``core`` reports: codes with params and a location, never text (decision 0009).

The message and hint of each code live in the catalogs in ``i18n/``, in every language; the UI,
the CLI and the MCP server render them. ``core`` reports every problem it finds as an ``Issue``
value: it never raises for something wrong in a project.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
from uuid import UUID

type ParamScalar = str | int | float | bool
# Lists (pins, allowed values) stay tuples: the UI joins them for the user's language.
type ParamValue = ParamScalar | tuple[ParamScalar, ...]


class CoreErrorCode(StrEnum):
    """Every code ``core`` can report, each with its params. Renaming one breaks the contract."""

    FILE_NOT_UTF8 = "file.not_utf8"
    FILE_INVALID_JSON = "file.invalid_json"  # line, column
    FILE_DUPLICATE_KEY = "file.duplicate_key"  # key
    FILE_NOT_AN_OBJECT = "file.not_an_object"
    SCHEMA_MISSING_FIELD = "schema.missing_field"  # field
    SCHEMA_UNKNOWN_FIELD = "schema.unknown_field"  # field
    SCHEMA_WRONG_TYPE = "schema.wrong_type"  # field, expected
    SCHEMA_NOT_ALLOWED = "schema.not_allowed"  # field, allowed
    SCHEMA_INVALID_FORMAT = "schema.invalid_format"  # field, format
    SCHEMA_INVALID_VALUE = "schema.invalid_value"  # field
    SCHEMA_TOO_SHORT = "schema.too_short"  # field, min
    SCHEMA_TOO_LONG = "schema.too_long"  # field, max
    SCHEMA_TOO_FEW_ITEMS = "schema.too_few_items"  # field, min
    SCHEMA_TOO_MANY_ITEMS = "schema.too_many_items"  # field, max
    SCHEMA_DUPLICATE_ITEMS = "schema.duplicate_items"  # field
    SCHEMA_BELOW_MINIMUM = "schema.below_minimum"  # field, minimum
    SCHEMA_ABOVE_MAXIMUM = "schema.above_maximum"  # field, maximum
    SCHEMA_UNSUPPORTED_VERSION = "schema.unsupported_version"  # version, supported


class Severity(StrEnum):
    """An error makes a project invalid; a warning is worth a look but does not."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Location:
    """Where a problem is: a file and a JSON Pointer inside it ("" is the whole file).

    ``file_id`` is the file's id once it is known: it identifies the file for good. ``path`` is
    where the caller found it, for display only (files reference each other by id).
    """

    path: PurePosixPath
    pointer: str = ""
    file_id: UUID | None = None


@dataclass(frozen=True)
class Issue:
    code: CoreErrorCode
    params: Mapping[str, ParamValue] = field(default_factory=dict[str, ParamValue])
    location: Location | None = None
    severity: Severity = Severity.ERROR
