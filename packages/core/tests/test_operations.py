"""Editing a project: what an operation changes, and what refuses it."""

import json
from pathlib import PurePosixPath
from uuid import UUID

import pytest

from primum_core.errors import CoreErrorCode, Issue
from primum_core.json_values import as_list, as_object
from primum_core.operations import apply_operation

type Files = dict[PurePosixPath, bytes]
type Found = list[tuple[CoreErrorCode, dict[str, object], str | None]]

MANIFEST = PurePosixPath("project.json")
VARS = PurePosixPath("shop.vars")
INNER_VARS = PurePosixPath("night/night.vars")
PROJECT, VARS_ID, INNER_ID, BRIGHTNESS, GREETING, VISITS = (str(UUID(int=n)) for n in range(1, 7))


def _file(kind: str, id_: str, **fields: object) -> bytes:
    return json.dumps({"id": id_, "kind": kind, "schemaVersion": 1, **fields}).encode()


def _project() -> Files:
    brightness = {
        "id": BRIGHTNESS,
        "name": "brightness",
        "type": "integer",
        "initial": 80,
        "min": 0,
        "max": 100,
    }
    greeting = {"id": GREETING, "name": "greeting", "type": "text", "initial": "hello"}
    visits = {"id": VISITS, "name": "visits", "type": "number", "initial": 0}
    return {
        MANIFEST: _file("project", PROJECT, name="Shop window", description="The shop"),
        VARS: _file("variables", VARS_ID, constants=[], variables=[brightness, greeting]),
        INNER_VARS: _file("variables", INNER_ID, constants=[], variables=[visits]),
    }


def _document(files: Files | None, path: PurePosixPath) -> dict[str, object]:
    assert files is not None
    return dict(as_object(json.loads(files[path])))


def _variable(files: Files | None, path: PurePosixPath, index: int) -> dict[str, object]:
    return dict(as_object(as_list(_document(files, path)["variables"])[index]))


def _applied(operation: object, files: Files | None = None) -> Files:
    result = apply_operation(files or _project(), operation)
    assert result.value is not None, result.issues
    assert result.issues == ()
    return dict(result.value)


def _refused(operation: object, files: Files | None = None) -> Found:
    result = apply_operation(files or _project(), operation)
    assert result.value is None
    return [_flat(issue) for issue in result.issues]


def _flat(issue: Issue) -> tuple[CoreErrorCode, dict[str, object], str | None]:
    return (issue.code, dict(issue.params), issue.location and issue.location.pointer)


def test_set_project_with_a_name_changes_the_name_in_the_manifest() -> None:
    files = _applied({"op": "set_project", "name": "Window"})

    assert _document(files, MANIFEST)["name"] == "Window"


def test_set_project_keeps_the_fields_it_does_not_name() -> None:
    files = _applied({"op": "set_project", "timeZone": "Europe/Madrid"})

    assert _document(files, MANIFEST) == {
        "id": PROJECT,
        "kind": "project",
        "schemaVersion": 1,
        "name": "Shop window",
        "description": "The shop",
        "timeZone": "Europe/Madrid",
    }


def test_set_project_clearing_the_description_takes_it_away() -> None:
    files = _applied({"op": "set_project", "clear": ["description"]})

    assert "description" not in _document(files, MANIFEST)


def test_an_operation_does_not_change_the_files_it_was_given() -> None:
    files = _project()
    given = dict(files)

    apply_operation(files, {"op": "set_project", "name": "Window"})

    assert files == given


def test_an_operation_gives_back_the_other_files_as_they_were() -> None:
    before = _project()

    after = _applied({"op": "set_project", "name": "Window"}, before)

    assert after[VARS] is before[VARS]
    assert after[INNER_VARS] is before[INNER_VARS]


def test_a_changed_file_is_written_with_its_fields_in_the_order_of_the_schema() -> None:
    files = _applied({"op": "set_variable", "variable": BRIGHTNESS, "label": "Brightness"})

    written = list(_variable(files, VARS, 0))
    assert written == ["id", "name", "type", "initial", "label", "min", "max"]


def test_a_changed_file_is_written_as_utf8_with_a_line_end() -> None:
    files = _applied({"op": "set_project", "name": "Señal ☀"})

    assert "Señal ☀".encode() in files[MANIFEST]
    assert files[MANIFEST].endswith(b"}\n")


def test_set_variable_changes_the_variable_with_that_id_wherever_its_file_is() -> None:
    files = _applied({"op": "set_variable", "variable": VISITS, "initial": 5, "persistent": True})

    visits = _variable(files, INNER_VARS, 0)
    assert (visits["initial"], visits["persistent"]) == (5, True)


def test_set_variable_leaves_the_other_variables_of_the_file_alone() -> None:
    before = _project()

    files = _applied({"op": "set_variable", "variable": BRIGHTNESS, "max": 90, "step": 5}, before)

    assert _variable(files, VARS, 1) == _variable(before, VARS, 1)
    assert _variable(files, VARS, 0)["max"] == 90
    assert _variable(files, VARS, 0)["step"] == 5


def test_set_variable_can_move_both_limits_and_the_initial_value_at_once() -> None:
    operation = {"op": "set_variable", "variable": BRIGHTNESS, "min": 200, "max": 300}

    files = _applied({**operation, "initial": 250})

    assert _variable(files, VARS, 0)["initial"] == 250


def test_set_variable_clearing_a_limit_takes_it_away() -> None:
    files = _applied({"op": "set_variable", "variable": BRIGHTNESS, "clear": ["max"]})

    assert "max" not in _variable(files, VARS, 0)


def test_set_variable_with_the_id_in_capitals_finds_the_variable() -> None:
    files = _applied({"op": "set_variable", "variable": VISITS.upper(), "initial": 1})

    assert _variable(files, INNER_VARS, 0)["initial"] == 1


NO_PARAMS: dict[str, object] = {}
WRONG_SHAPES: list[tuple[object, tuple[CoreErrorCode, dict[str, object], None]]] = [
    ("set_project", (CoreErrorCode.FILE_NOT_AN_OBJECT, NO_PARAMS, None)),
    (NO_PARAMS, (CoreErrorCode.SCHEMA_MISSING_FIELD, {"field": "op"}, None)),
    (
        {"op": "delete_everything"},
        (
            CoreErrorCode.SCHEMA_NOT_ALLOWED,
            {"field": "op", "allowed": ("set_project", "set_variable")},
            None,
        ),
    ),
    (
        {"op": "set_project", "name": ""},
        (CoreErrorCode.SCHEMA_TOO_SHORT, {"field": "name", "min": 1}, None),
    ),
    (
        {"op": "set_project", "colour": "red"},
        (CoreErrorCode.SCHEMA_UNKNOWN_FIELD, {"field": "colour"}, None),
    ),
    (
        {"op": "set_project", "name": "half \ud83d"},
        (CoreErrorCode.OPERATION_INVALID_TEXT, NO_PARAMS, None),
    ),
]


@pytest.mark.parametrize(("operation", "expected"), WRONG_SHAPES)
def test_an_operation_of_the_wrong_shape_is_refused_pointing_at_no_file(
    operation: object, expected: tuple[CoreErrorCode, dict[str, object], None]
) -> None:
    assert _refused(operation) == [expected]


def test_a_field_of_another_op_is_refused() -> None:
    found = _refused({"op": "set_project", "name": "Window", "step": 2})

    assert found == [(CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, {"field": "step"}, None)]


def test_set_variable_without_the_variable_is_refused() -> None:
    found = _refused({"op": "set_variable", "initial": 3})

    assert found == [(CoreErrorCode.SCHEMA_MISSING_FIELD, {"field": "variable"}, None)]


def test_clearing_a_field_the_op_cannot_clear_is_refused() -> None:
    found = _refused({"op": "set_variable", "variable": VISITS, "clear": ["description"]})

    assert found == [(CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, {"field": "clear[0]"}, None)]


def test_a_field_both_set_and_cleared_is_refused() -> None:
    found = _refused({"op": "set_variable", "variable": VISITS, "max": 9, "clear": ["max"]})

    assert found == [(CoreErrorCode.OPERATION_SET_AND_CLEARED, {"field": "max"}, None)]


def test_set_variable_with_an_id_that_is_not_in_the_project_is_refused() -> None:
    missing = str(UUID(int=99))

    found = _refused({"op": "set_variable", "variable": missing, "initial": 1})

    assert found == [(CoreErrorCode.OPERATION_UNKNOWN_VARIABLE, {"id": missing}, None)]


def test_set_variable_does_not_find_a_variable_in_a_file_that_cannot_be_read() -> None:
    files = _project()
    files[INNER_VARS] = b"{ not json"

    found = _refused({"op": "set_variable", "variable": VISITS, "initial": 1}, files)

    assert found == [(CoreErrorCode.OPERATION_UNKNOWN_VARIABLE, {"id": VISITS}, None)]


def test_set_project_without_a_manifest_is_refused() -> None:
    files = _project()
    del files[MANIFEST]

    found = _refused({"op": "set_project", "name": "Window"}, files)

    assert found == [(CoreErrorCode.PROJECT_MANIFEST_MISSING, {}, "")]


def test_set_project_on_a_manifest_that_cannot_be_read_is_refused_with_its_problem() -> None:
    files = _project()
    files[MANIFEST] = _file("project", PROJECT)

    found = _refused({"op": "set_project", "name": "Window"}, files)

    assert found == [(CoreErrorCode.SCHEMA_MISSING_FIELD, {"field": "name"}, "")]


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (
            {"min": 200},
            (
                CoreErrorCode.VARIABLE_LIMITS_INVALID,
                {"name": "brightness", "min": 200, "max": 100},
                "/variables/0",
            ),
        ),
        (
            {"initial": 101},
            (
                CoreErrorCode.VARIABLE_INITIAL_OUT_OF_RANGE,
                {"name": "brightness", "initial": 101},
                "/variables/0",
            ),
        ),
        (
            {"initial": "bright"},
            (
                CoreErrorCode.VALUE_EXPECTED_INTEGER,
                {"field": "variables[0].initial"},
                "/variables/0/initial",
            ),
        ),
        (
            {"step": 0},
            (
                CoreErrorCode.VARIABLE_STEP_INVALID,
                {"name": "brightness", "step": 0},
                "/variables/0",
            ),
        ),
        (
            {"step": 0.5},
            (
                CoreErrorCode.VARIABLE_STEP_INVALID,
                {"name": "brightness", "step": 0.5},
                "/variables/0",
            ),
        ),
    ],
)
def test_set_variable_that_would_leave_its_file_with_a_new_problem_is_refused(
    change: dict[str, object], expected: tuple[CoreErrorCode, dict[str, object], str]
) -> None:
    assert _refused({"op": "set_variable", "variable": BRIGHTNESS, **change}) == [expected]


def test_set_variable_with_a_limit_on_a_text_is_refused() -> None:
    found = _refused({"op": "set_variable", "variable": GREETING, "max": 3})

    expected = (
        CoreErrorCode.SCHEMA_UNEXPECTED_FIELD,
        {"field": "variables[1].max"},
        "/variables/1/max",
    )
    assert found == [expected]


def test_a_problem_the_file_already_had_does_not_refuse_an_operation_on_it() -> None:
    files = _project()
    backwards = {"id": VISITS, "name": "visits", "type": "number", "initial": 5, "min": 9, "max": 1}
    files[INNER_VARS] = _file("variables", INNER_ID, constants=[], variables=[backwards])

    after = _applied({"op": "set_variable", "variable": VISITS, "label": "Visits"}, files)

    assert _variable(after, INNER_VARS, 0)["label"] == "Visits"


def test_an_operation_may_leave_the_project_with_a_problem_outside_its_file() -> None:
    """A time zone no board knows is for ``load_workspace`` to say, not a reason to refuse."""
    files = _applied({"op": "set_project", "timeZone": "Mars/Olympus"})

    assert _document(files, MANIFEST)["timeZone"] == "Mars/Olympus"
