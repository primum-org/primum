"""Constants and variables: a value of the declared type, limits that make sense."""

import pytest

from primum_core.errors import CoreErrorCode, Severity
from project_builder import Ids, Project


def _vars(
    project: Project, ids: Ids, **fields: object
) -> list[tuple[CoreErrorCode, dict[str, object], str, str]]:
    document: dict[str, object] = {"constants": [], "variables": [], **fields}
    project.add("shop.vars", "variables", ids(10), **document)
    return project.found(severity=Severity.ERROR)


@pytest.mark.parametrize(
    ("value_type", "value", "code"),
    [
        ("integer", 2.5, CoreErrorCode.VALUE_EXPECTED_INTEGER),
        ("integer", "2", CoreErrorCode.VALUE_EXPECTED_INTEGER),
        ("integer", True, CoreErrorCode.VALUE_EXPECTED_INTEGER),
        ("number", True, CoreErrorCode.VALUE_EXPECTED_NUMBER),
        ("number", "0.5", CoreErrorCode.VALUE_EXPECTED_NUMBER),
        ("boolean", 1, CoreErrorCode.VALUE_EXPECTED_BOOLEAN),
        ("text", 3, CoreErrorCode.VALUE_EXPECTED_TEXT),
    ],
)
def test_a_constant_holds_a_value_of_its_type(
    project: Project, ids: Ids, value_type: str, value: object, code: CoreErrorCode
) -> None:
    constants = [{"id": ids(11), "name": "speed", "type": value_type, "value": value}]

    assert _vars(project, ids, constants=constants) == [
        (code, {"field": "constants[0].value"}, "shop.vars", "/constants/0/value")
    ]


@pytest.mark.parametrize(
    ("value_type", "value"),
    [("integer", 2), ("number", 2), ("number", 0.5), ("boolean", False), ("text", "night")],
)
def test_values_of_the_declared_type_pass(
    project: Project, ids: Ids, value_type: str, value: object
) -> None:
    constants = [{"id": ids(11), "name": "speed", "type": value_type, "value": value}]

    assert _vars(project, ids, constants=constants) == []


def test_a_variable_starts_with_a_value_of_its_type(project: Project, ids: Ids) -> None:
    variables = [{"id": ids(11), "name": "count", "type": "integer", "initial": "0"}]

    assert _vars(project, ids, variables=variables) == [
        (
            CoreErrorCode.VALUE_EXPECTED_INTEGER,
            {"field": "variables[0].initial"},
            "shop.vars",
            "/variables/0/initial",
        )
    ]


def test_only_a_numeric_variable_has_limits(project: Project, ids: Ids) -> None:
    variables = [{"id": ids(11), "name": "mode", "type": "text", "initial": "a", "min": 0}]

    assert _vars(project, ids, variables=variables) == [
        (
            CoreErrorCode.SCHEMA_UNEXPECTED_FIELD,
            {"field": "variables[0].min"},
            "shop.vars",
            "/variables/0/min",
        )
    ]


def test_limits_the_wrong_way_round_are_reported(project: Project, ids: Ids) -> None:
    variables = [{"id": ids(11), "name": "n", "type": "integer", "initial": 5, "min": 9, "max": 1}]

    assert _vars(project, ids, variables=variables) == [
        (
            CoreErrorCode.VARIABLE_LIMITS_INVALID,
            {"name": "n", "min": 9, "max": 1},
            "shop.vars",
            "/variables/0",
        )
    ]


@pytest.mark.parametrize("initial", [-1, 11])
def test_the_initial_value_lies_within_the_limits(project: Project, ids: Ids, initial: int) -> None:
    variables = [
        {"id": ids(11), "name": "n", "type": "integer", "initial": initial, "min": 0, "max": 10}
    ]

    assert _vars(project, ids, variables=variables) == [
        (
            CoreErrorCode.VARIABLE_INITIAL_OUT_OF_RANGE,
            {"name": "n", "initial": initial},
            "shop.vars",
            "/variables/0",
        )
    ]


def test_an_initial_value_on_a_limit_is_within_it(project: Project, ids: Ids) -> None:
    variables = [{"id": ids(11), "name": "n", "type": "number", "initial": 10, "max": 10}]

    assert _vars(project, ids, variables=variables) == []
