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
    FILE_NOT_IN_FORMAT = "file.not_in_format"  # (warning) a file of no project type, ignored
    PROJECT_MANIFEST_MISSING = "project.manifest_missing"
    ID_DUPLICATE = "id.duplicate"  # id
    REF_UNKNOWN = "ref.unknown"  # field, id
    REF_WRONG_KIND = "ref.wrong_kind"  # field, id
    # Constants, variables and the scopes of their names (decision 0005).
    NAME_REDEFINED = "name.redefined"  # name, other (the path that already defines it)
    NAME_UNKNOWN = "name.unknown"  # name
    NAME_NOT_EXPORTED = "name.not_exported"  # name
    NAME_NOT_A_VARIABLE = "name.not_a_variable"  # name
    NAME_UNUSED = "name.unused"  # (warning) name
    VALUE_EXPECTED_NUMBER = "value.expected_number"  # field
    VALUE_EXPECTED_INTEGER = "value.expected_integer"  # field
    VALUE_EXPECTED_BOOLEAN = "value.expected_boolean"  # field
    VALUE_EXPECTED_TEXT = "value.expected_text"  # field
    VARIABLE_LIMITS_INVALID = "variable.limits_invalid"  # name, min, max
    VARIABLE_INITIAL_OUT_OF_RANGE = "variable.initial_out_of_range"  # name, initial
    VARIABLE_NOT_NUMERIC = "variable.not_numeric"  # name
    # Components: sequences with parameters, included with arguments.
    ARGUMENT_MISSING = "argument.missing"  # parameter
    ARGUMENT_DUPLICATE = "argument.duplicate"  # parameter
    ARGUMENT_EXPECTED_ELEMENT = "argument.expected_element"  # parameter
    ARGUMENT_EXPECTED_VALUE = "argument.expected_value"  # parameter
    SEQUENCE_INCLUDES_ITSELF = "sequence.includes_itself"  # sequence
    SEQUENCE_CYCLE = "sequence.cycle"  # sequence, chain
    SCHEMA_MISSING_FIELD = "schema.missing_field"  # field
    SCHEMA_UNKNOWN_FIELD = "schema.unknown_field"  # field
    SCHEMA_UNEXPECTED_FIELD = "schema.unexpected_field"  # field: of the format, not of this case
    # A value of the wrong type: one code per expected type, so every message reads naturally
    # in every language instead of quoting JSON Schema's type names.
    SCHEMA_EXPECTED_TEXT = "schema.expected_text"  # field
    SCHEMA_EXPECTED_INTEGER = "schema.expected_integer"  # field
    SCHEMA_EXPECTED_NUMBER = "schema.expected_number"  # field
    SCHEMA_EXPECTED_BOOLEAN = "schema.expected_boolean"  # field
    SCHEMA_EXPECTED_LIST = "schema.expected_list"  # field
    SCHEMA_EXPECTED_OBJECT = "schema.expected_object"  # field
    SCHEMA_NOT_ALLOWED = "schema.not_allowed"  # field, allowed
    SCHEMA_INVALID_ID = "schema.invalid_id"  # field
    SCHEMA_INVALID_VALUE = "schema.invalid_value"  # field
    SCHEMA_TOO_SHORT = "schema.too_short"  # field, min
    SCHEMA_TOO_LONG = "schema.too_long"  # field, max
    SCHEMA_TOO_FEW_ITEMS = "schema.too_few_items"  # field, min
    SCHEMA_TOO_MANY_ITEMS = "schema.too_many_items"  # field, max
    SCHEMA_DUPLICATE_ITEMS = "schema.duplicate_items"  # field
    SCHEMA_BELOW_MINIMUM = "schema.below_minimum"  # field, minimum
    SCHEMA_ABOVE_MAXIMUM = "schema.above_maximum"  # field, maximum
    SCHEMA_UNSUPPORTED_VERSION = "schema.unsupported_version"  # version, supported
    BOARD_DUPLICATE_PIN = "board.duplicate_pin"  # physical
    BOARD_POWER_PIN_WITH_GPIO = "board.power_pin_with_gpio"  # physical
    BOARD_INCOMPLETE_GPIO_PIN = "board.incomplete_gpio_pin"  # physical
    BOARD_DUPLICATE_GPIO = "board.duplicate_gpio"  # gpio
    BOARD_DUPLICATE_LINE = "board.duplicate_line"  # line
    BOARD_UNKNOWN_GPIO = "board.unknown_gpio"  # gpio
    BOARD_DUPLICATE_ID = "board.duplicate_id"  # id


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
    """One problem found in a project. Equal issues hash alike, so they can be deduplicated."""

    code: CoreErrorCode
    params: Mapping[str, ParamValue] = field(default_factory=dict[str, ParamValue])
    location: Location | None = None
    severity: Severity = Severity.ERROR

    # Written by hand because params is a mapping; dataclass keeps an explicit __hash__.
    def __hash__(self) -> int:
        return hash((self.code, frozenset(self.params.items()), self.location, self.severity))
