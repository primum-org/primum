"""Driver manifests: the shipped ones read, and what a manifest means beyond its schema."""

import json
from pathlib import PurePosixPath

import pytest

from primum_core.errors import CoreErrorCode
from primum_core.formats import read_driver, read_drivers
from project_builder import DRIVERS, DRIVERS_FOLDER, ROOT, driver_manifest


def _found(**fields: object) -> list[tuple[CoreErrorCode, dict[str, object], str]]:
    document = json.dumps(driver_manifest("lamp", **fields)).encode()
    parsed = read_driver(PurePosixPath("lamp.json"), document)
    return [
        (issue.code, dict(issue.params), issue.location.pointer if issue.location else "")
        for issue in parsed.issues
    ]


def _action(name: str, *parameters: dict[str, object]) -> dict[str, object]:
    return {"name": name, "parameters": list(parameters), "endState": 100}


def test_the_shipped_drivers_are_the_three_of_this_phase() -> None:
    assert sorted(DRIVERS) == ["digital_input", "digital_output", "pwm_output"]


def test_each_shipped_driver_is_of_an_element_type_and_its_file_is_named_after_it() -> None:
    schema = json.loads((ROOT / "schemas" / "hardware.schema.json").read_text())
    element_types: list[str] = schema["$defs"]["element"]["properties"]["type"]["enum"]

    for path in sorted(DRIVERS_FOLDER.glob("*.json")):
        manifest = json.loads(path.read_text())
        assert manifest["elementType"] == path.stem
        assert manifest["elementType"] in element_types


def test_an_output_rests_in_one_of_its_actions_and_an_input_has_none() -> None:
    assert DRIVERS["digital_output"].safe_state == "off"
    assert DRIVERS["pwm_output"].safe_state == "off"
    assert DRIVERS["digital_input"].actions == ()
    assert DRIVERS["digital_input"].safe_state is None


def test_each_shipped_action_says_the_state_it_leaves_its_element_in() -> None:
    states = {
        (name, action.name): (action.start_state, action.end_state)
        for name, manifest in DRIVERS.items()
        for action in manifest.actions
    }

    assert states == {
        ("digital_output", "on"): (None, 100),
        ("digital_output", "off"): (None, 0),
        ("pwm_output", "on"): (None, 100),
        ("pwm_output", "off"): (None, 0),
        ("pwm_output", "set"): (None, "level"),
        ("pwm_output", "fade"): ("from", "to"),
    }


def test_no_shipped_option_carries_a_limit_that_is_its_board_s() -> None:
    frequency = DRIVERS["pwm_output"].config[0]

    assert (frequency.name, frequency.min, frequency.max) == ("frequencyHz", None, None)


@pytest.mark.parametrize(
    ("field", "parameters"),
    [
        ("endState", []),  # no such parameter
        ("startState", [{"name": "level", "type": "text", "default": "high"}]),  # not a number
    ],
)
def test_a_state_given_by_a_parameter_names_a_number_of_the_action(
    field: str, parameters: list[dict[str, object]]
) -> None:
    action = {**_action("on", *parameters), field: "level"}

    assert _found(actions=[action]) == [
        (
            CoreErrorCode.DRIVER_UNKNOWN_STATE_PARAMETER,
            {"action": "on", "parameter": "level"},
            f"/actions/0/{field}",
        )
    ]


def test_a_state_given_by_a_number_of_the_action() -> None:
    level: dict[str, object] = {"name": "level", "type": "number", "default": 100}

    assert _found(actions=[{**_action("on", level), "endState": "level"}]) == []


def test_a_fixed_state_is_a_level_from_0_to_100() -> None:
    assert _found(actions=[{**_action("on"), "endState": 101}]) == [
        (
            CoreErrorCode.SCHEMA_ABOVE_MAXIMUM,
            {"field": "actions[0].endState", "maximum": 100},
            "/actions/0/endState",
        )
    ]


def test_the_manifests_are_read_together_each_by_its_own_type() -> None:
    files = {PurePosixPath(path.name): path.read_bytes() for path in DRIVERS_FOLDER.glob("*.json")}
    files[PurePosixPath("renamed.json")] = files.pop(PurePosixPath("pwm_output.json"))

    parsed = read_drivers(files)

    assert parsed.issues == ()
    assert parsed.value == DRIVERS


def test_two_manifests_of_one_type_are_refused() -> None:
    lamp = json.dumps(driver_manifest("lamp")).encode()

    parsed = read_drivers({PurePosixPath("a.json"): lamp, PurePosixPath("b.json"): lamp})

    assert parsed.value is None
    assert [(issue.code, dict(issue.params)) for issue in parsed.issues] == [
        (CoreErrorCode.DRIVER_DUPLICATE_TYPE, {"type": "lamp"})
    ]


def test_a_broken_manifest_stops_them_all() -> None:
    files = {PurePosixPath("lamp.json"): b"{}"}

    assert read_drivers(files).value is None


def test_a_manifest_as_the_tests_build_it_is_valid() -> None:
    assert _found() == []


def test_an_action_declared_twice() -> None:
    assert _found(actions=[_action("on"), _action("on")]) == [
        (CoreErrorCode.DRIVER_DUPLICATE_ACTION, {"action": "on"}, "/actions/1/name")
    ]


def test_a_parameter_declared_twice_in_one_action() -> None:
    level: dict[str, object] = {"name": "level", "type": "number", "default": 0}

    assert _found(actions=[_action("on", level, level)]) == [
        (
            CoreErrorCode.DRIVER_DUPLICATE_PARAMETER,
            {"parameter": "level"},
            "/actions/0/parameters/1/name",
        )
    ]


def test_two_actions_may_each_have_a_parameter_of_the_same_name() -> None:
    level: dict[str, object] = {"name": "level", "type": "number", "default": 0}

    assert _found(actions=[_action("on", level), _action("dim", level)]) == []


@pytest.mark.parametrize(
    ("parameter", "expected"),
    [
        (
            {"name": "level", "type": "number", "min": 100, "max": 0, "default": 50},
            (
                CoreErrorCode.DRIVER_LIMITS_INVALID,
                {"parameter": "level", "min": 100, "max": 0},
                "/config/0",
            ),
        ),
        (
            {"name": "steps", "type": "integer", "min": 0.5, "max": 10, "default": 5},
            (
                CoreErrorCode.VALUE_EXPECTED_INTEGER,
                {"field": "config[0].min"},
                "/config/0/min",
            ),
        ),
        (
            {"name": "level", "type": "number", "min": 0, "default": 50},
            (CoreErrorCode.SCHEMA_MISSING_FIELD, {"field": "config[0].max"}, "/config/0"),
        ),
        (
            {"name": "pull", "type": "text", "min": 0, "max": 1, "default": "up"},
            (CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, {"field": "config[0].min"}, "/config/0/min"),
        ),
        (
            {"name": "level", "type": "number", "choices": ["low", "high"], "default": 1},
            (
                CoreErrorCode.SCHEMA_UNEXPECTED_FIELD,
                {"field": "config[0].choices"},
                "/config/0/choices",
            ),
        ),
        (
            {"name": "level", "type": "number", "default": "half"},
            (
                CoreErrorCode.VALUE_EXPECTED_NUMBER,
                {"field": "config[0].default"},
                "/config/0/default",
            ),
        ),
        (
            {"name": "level", "type": "number", "min": 0, "max": 100, "default": 150},
            (
                CoreErrorCode.DRIVER_DEFAULT_NOT_ALLOWED,
                {"parameter": "level"},
                "/config/0/default",
            ),
        ),
        (
            {"name": "pull", "type": "text", "choices": ["up", "down"], "default": "sideways"},
            (
                CoreErrorCode.DRIVER_DEFAULT_NOT_ALLOWED,
                {"parameter": "pull"},
                "/config/0/default",
            ),
        ),
    ],
)
def test_a_parameter_that_contradicts_itself(
    parameter: dict[str, object], expected: tuple[CoreErrorCode, dict[str, object], str]
) -> None:
    assert expected in _found(config=[parameter])


def test_a_driver_with_actions_says_where_it_rests_and_who_wins_a_conflict() -> None:
    manifest = driver_manifest("lamp")
    del manifest["safeState"]
    del manifest["conflictPolicy"]
    parsed = read_driver(PurePosixPath("lamp.json"), json.dumps(manifest).encode())

    assert [(issue.code, dict(issue.params)) for issue in parsed.issues] == [
        (CoreErrorCode.SCHEMA_MISSING_FIELD, {"field": "conflictPolicy"}),
        (CoreErrorCode.SCHEMA_MISSING_FIELD, {"field": "safeState"}),
    ]


def test_a_driver_without_actions_says_neither() -> None:
    assert _found(actions=[]) == [
        (CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, {"field": "conflictPolicy"}, "/conflictPolicy"),
        (CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, {"field": "safeState"}, "/safeState"),
    ]


@pytest.mark.parametrize(
    "actions",
    [
        [_action("on")],  # "off" is not one of them
        [_action("on"), _action("off", {"name": "level", "type": "number"})],  # needs a level
    ],
)
def test_the_safe_state_is_an_action_that_runs_without_arguments(
    actions: list[dict[str, object]],
) -> None:
    assert _found(actions=actions, safeState="off") == [
        (CoreErrorCode.DRIVER_UNKNOWN_SAFE_STATE, {"action": "off"}, "/safeState")
    ]


def test_a_limit_no_float_holds_is_reported_not_raised() -> None:
    parameter = {"name": "steps", "type": "integer", "min": 0, "max": 10**400, "default": 5}

    assert _found(config=[parameter]) == [
        (CoreErrorCode.SCHEMA_EXPECTED_NUMBER, {"field": "config[0].max"}, "/config/0/max")
    ]


def test_a_state_names_a_parameter_as_parameters_are_named() -> None:
    """``actionState`` is a number or a name, so it cannot refer to ``parameterName``: it
    repeats its rules, and they must stay the same."""
    schemas = ROOT / "schemas"
    state = json.loads((schemas / "driver.schema.json").read_text())["$defs"]["actionState"]
    name = json.loads((schemas / "common.schema.json").read_text())["$defs"]["parameterName"]

    assert [state[rule] for rule in ("pattern", "maxLength")] == [
        name[rule] for rule in ("pattern", "maxLength")
    ]
