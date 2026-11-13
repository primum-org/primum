"""Reading files: text and JSON, structure against the schema, then the typed value."""

import json
from pathlib import PurePosixPath
from uuid import UUID

import pytest

from primum_core.errors import CoreErrorCode, Issue, Location, Severity
from primum_core.formats import read_manifest, read_project_file
from primum_core.generated.model import Project

PATH = PurePosixPath("project.json")
PROJECT_ID = "8d0f6f1e-3b2a-4c55-9a51-1f2d3c4b5a69"


def _manifest(**changes: object) -> bytes:
    document: dict[str, object] = {
        "id": PROJECT_ID,
        "kind": "project",
        "schemaVersion": 1,
        "name": "Shop window",
    }
    document.update(changes)
    return json.dumps(document).encode()


def _codes(content: bytes) -> list[tuple[CoreErrorCode, dict[str, object], str]]:
    parsed = read_manifest(PATH, content)
    assert parsed.value is None
    return [
        (issue.code, dict(issue.params), issue.location.pointer if issue.location else "")
        for issue in parsed.issues
    ]


def test_a_valid_manifest_gives_the_project() -> None:
    parsed = read_manifest(PATH, _manifest(description="Lights for the window"))

    assert parsed.issues == ()
    assert parsed.value == Project(
        id=UUID(PROJECT_ID), name="Shop window", description="Lights for the window"
    )


def test_optional_fields_are_none_when_absent() -> None:
    parsed = read_manifest(PATH, _manifest())

    assert parsed.value is not None
    assert parsed.value.description is None


def test_a_byte_order_mark_is_accepted() -> None:
    parsed = read_manifest(PATH, b"\xef\xbb\xbf" + _manifest())

    assert parsed.value is not None


def test_text_that_is_not_utf8_is_reported() -> None:
    assert _codes(b"\xff\xfe") == [(CoreErrorCode.FILE_NOT_UTF8, {}, "")]


def test_invalid_json_is_reported_with_its_position() -> None:
    assert _codes(b'{\n  "name": \n') == [
        (CoreErrorCode.FILE_INVALID_JSON, {"line": 3, "column": 1}, "")
    ]


def test_a_repeated_key_is_reported_instead_of_keeping_the_last_one() -> None:
    content = b'{"name": "a", "name": "b"}'

    assert _codes(content) == [(CoreErrorCode.FILE_DUPLICATE_KEY, {"key": "name"}, "")]


def test_a_document_that_is_not_an_object_is_reported() -> None:
    assert _codes(b"[1, 2]") == [(CoreErrorCode.FILE_NOT_AN_OBJECT, {}, "")]


def test_every_missing_field_is_reported_at_its_object() -> None:
    content = json.dumps({"kind": "project"}).encode()

    assert _codes(content) == [
        (CoreErrorCode.SCHEMA_MISSING_FIELD, {"field": "id"}, ""),
        (CoreErrorCode.SCHEMA_MISSING_FIELD, {"field": "schemaVersion"}, ""),
        (CoreErrorCode.SCHEMA_MISSING_FIELD, {"field": "name"}, ""),
    ]


def test_every_problem_is_reported_not_only_the_first() -> None:
    content = _manifest(id="not-a-uuid", name="", extra=1, other=2)

    assert _codes(content) == [
        (CoreErrorCode.SCHEMA_INVALID_ID, {"field": "id"}, "/id"),
        (CoreErrorCode.SCHEMA_TOO_SHORT, {"field": "name", "min": 1}, "/name"),
        (CoreErrorCode.SCHEMA_UNKNOWN_FIELD, {"field": "extra"}, "/extra"),
        (CoreErrorCode.SCHEMA_UNKNOWN_FIELD, {"field": "other"}, "/other"),
    ]


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"name": 3}, (CoreErrorCode.SCHEMA_EXPECTED_TEXT, {"field": "name"})),
        ({"name": "x" * 81}, (CoreErrorCode.SCHEMA_TOO_LONG, {"field": "name", "max": 80})),
        (
            {"kind": "sequence"},
            (CoreErrorCode.SCHEMA_NOT_ALLOWED, {"field": "kind", "allowed": ("project",)}),
        ),
        (
            {"schemaVersion": 2},
            (CoreErrorCode.SCHEMA_UNSUPPORTED_VERSION, {"version": 2, "supported": 1}),
        ),
        (
            {"schemaVersion": "1"},
            (CoreErrorCode.SCHEMA_NOT_ALLOWED, {"field": "schemaVersion", "allowed": (1,)}),
        ),
    ],
)
def test_each_rule_has_its_code_and_params(
    changes: dict[str, object], expected: tuple[CoreErrorCode, dict[str, object]]
) -> None:
    [(code, params, pointer)] = _codes(_manifest(**changes))

    assert (code, params) == expected
    assert pointer == f"/{next(iter(changes))}"


HUGE = b"1" + b"0" * 400  # more than a float holds
ENDLESS = b"1" + b"0" * 5000  # more digits than Python converts


@pytest.mark.parametrize("number", [b"NaN", b"Infinity", b"-Infinity", b"1e400", HUGE, ENDLESS])
def test_numbers_json_does_not_have_are_reported_as_the_wrong_type(number: bytes) -> None:
    content = _manifest().replace(b'"Shop window"', number)

    assert _codes(content) == [(CoreErrorCode.SCHEMA_EXPECTED_TEXT, {"field": "name"}, "/name")]


def test_a_whole_number_written_with_decimals_is_an_integer() -> None:
    content = _manifest().replace(b'"schemaVersion": 1', b'"schemaVersion": 1.0')

    parsed = read_manifest(PATH, content)

    assert parsed.issues == ()


def test_a_whole_number_written_with_decimals_is_reported_as_an_integer() -> None:
    content = _manifest().replace(b'"schemaVersion": 1', b'"schemaVersion": 2e0')

    assert _codes(content) == [
        (CoreErrorCode.SCHEMA_UNSUPPORTED_VERSION, {"version": 2, "supported": 1}, "/schemaVersion")
    ]
    [issue] = read_manifest(PATH, content).issues
    assert type(issue.params["version"]) is int


def test_equal_issues_can_be_deduplicated() -> None:
    first = read_manifest(PATH, _manifest(name="")).issues
    second = read_manifest(PATH, _manifest(name="")).issues

    assert len(set(first + second)) == 1


def test_issues_name_the_file_by_path_and_by_id_once_known() -> None:
    parsed = read_manifest(PATH, _manifest(name=""))

    assert parsed.issues == (
        Issue(
            CoreErrorCode.SCHEMA_TOO_SHORT,
            {"field": "name", "min": 1},
            Location(PATH, "/name", UUID(PROJECT_ID)),
            Severity.ERROR,
        ),
    )


def test_without_a_valid_id_issues_name_the_file_by_path_only() -> None:
    parsed = read_manifest(PATH, _manifest(id="nope"))

    assert {issue.location for issue in parsed.issues} == {Location(PATH, "/id")}


def test_a_number_no_float_holds_in_a_project_file_is_reported_not_raised() -> None:
    variable = {"id": PROJECT_ID, "name": "visits", "type": "integer", "initial": 0, "min": 0}
    document = {
        "id": "7f4d431c-df59-402c-8b9e-d1614eb9fc27",
        "kind": "variables",
        "schemaVersion": 1,
        "constants": [],
        "variables": [variable],
    }
    content = json.dumps(document).encode().replace(b'"min": 0', b'"min": ' + HUGE)

    parsed = read_project_file(PurePosixPath("shop.vars"), content)

    assert [(issue.code, dict(issue.params)) for issue in parsed.issues] == [
        (CoreErrorCode.SCHEMA_EXPECTED_NUMBER, {"field": "variables[0].min"})
    ]
