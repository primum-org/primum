"""The configuration of each element, against the manifest of its driver."""

import pytest

from primum_core.errors import CoreErrorCode
from project_builder import Ids, Project, driver

BOARD = 3


def _element(ids: Ids, kind: str, pin: int, **options: object) -> dict[str, object]:
    element: dict[str, object] = {"id": ids(9), "name": "Thing", "board": ids(BOARD), "type": kind}
    element["pin"] = pin
    if options:
        element["config"] = [{"name": name, "value": value} for name, value in options.items()]
    return element


def _with(project: Project, ids: Ids, element: dict[str, object]) -> Project:
    return project.add("thing.hw", "hardware", ids(8), boards=[], elements=[element])


def test_the_options_a_driver_declares_within_their_limits(project: Project, ids: Ids) -> None:
    _with(project, ids, _element(ids, "pwm_output", 18, frequencyHz=25_000))

    assert project.found() == []


def test_an_input_takes_its_pull_and_its_debounce(project: Project, ids: Ids) -> None:
    _with(project, ids, _element(ids, "digital_input", 22, pull="none", debounceMs=0))

    assert project.found() == []


@pytest.mark.parametrize(
    ("kind", "pin", "options", "code", "params", "pointer"),
    [
        (
            "pwm_output",
            18,
            {"frequencyHz": 0},
            CoreErrorCode.CONFIG_OUT_OF_RANGE,
            {"option": "frequencyHz", "min": 1, "max": 100_000},
            "/elements/0/config/0/value",
        ),
        (
            "pwm_output",
            18,
            {"frequencyHz": 20_000_000},
            CoreErrorCode.CONFIG_OUT_OF_RANGE,
            {"option": "frequencyHz", "min": 1, "max": 100_000},
            "/elements/0/config/0/value",
        ),
        (
            "digital_input",
            22,
            {"pull": "up", "debounceMs": -5},
            CoreErrorCode.CONFIG_OUT_OF_RANGE,
            {"option": "debounceMs", "min": 0, "max": 10_000},
            "/elements/0/config/1/value",
        ),
        (
            "digital_input",
            22,
            {"pull": "sideways"},
            CoreErrorCode.CONFIG_NOT_ALLOWED,
            {"option": "pull", "allowed": ("up", "down", "none")},
            "/elements/0/config/0/value",
        ),
        (
            "digital_output",
            22,
            {"frequencyHz": 1000},
            CoreErrorCode.CONFIG_UNKNOWN,
            {"option": "frequencyHz"},
            "/elements/0/config/0",
        ),
    ],
)
def test_an_option_the_driver_does_not_take_as_given(
    project: Project,
    ids: Ids,
    kind: str,
    pin: int,
    options: dict[str, object],
    code: CoreErrorCode,
    params: dict[str, object],
    pointer: str,
) -> None:
    _with(project, ids, _element(ids, kind, pin, **options))

    assert project.found() == [(code, {"element": "Thing", **params}, "thing.hw", pointer)]


def test_an_option_of_another_type(project: Project, ids: Ids) -> None:
    _with(project, ids, _element(ids, "pwm_output", 18, frequencyHz=1000.5))

    assert project.found() == [
        (
            CoreErrorCode.VALUE_EXPECTED_INTEGER,
            {"field": "elements[0].config[0].value"},
            "thing.hw",
            "/elements/0/config/0/value",
        )
    ]


def test_an_option_given_twice(project: Project, ids: Ids) -> None:
    element = _element(ids, "pwm_output", 18)
    element["config"] = [
        {"name": "frequencyHz", "value": 500},
        {"name": "frequencyHz", "value": 1000},
    ]
    _with(project, ids, element)

    assert [(code, pointer) for code, _, _, pointer in project.found()] == [
        (CoreErrorCode.CONFIG_DUPLICATE, "/elements/0/config/1")
    ]


def test_an_option_without_a_default_must_be_given(project: Project, ids: Ids) -> None:
    count = {"name": "count", "type": "integer", "min": 1, "max": 300}
    project.drivers["pwm_output"] = driver("pwm_output", config=[count])
    _with(project, ids, _element(ids, "pwm_output", 18))

    assert project.found() == [
        (
            CoreErrorCode.CONFIG_MISSING,
            {"element": "Thing", "option": "count"},
            "thing.hw",
            "/elements/0",
        )
    ]


def test_an_element_whose_type_has_no_driver_takes_no_options(project: Project, ids: Ids) -> None:
    device: dict[str, object]
    device = {"id": ids(9), "name": "Screen", "board": ids(BOARD), "type": "i2c_device"}
    device |= {"bus": "i2c1", "address": 60, "config": [{"name": "contrast", "value": 5}]}
    _with(project, ids, device)

    assert project.found() == [
        (
            CoreErrorCode.CONFIG_UNKNOWN,
            {"element": "Screen", "option": "contrast"},
            "thing.hw",
            "/elements/0/config/0",
        )
    ]


def test_an_input_must_say_its_pull(project: Project, ids: Ids) -> None:
    _with(project, ids, _element(ids, "digital_input", 22, debounceMs=50))

    assert [(code, params) for code, params, *_ in project.found()] == [
        (CoreErrorCode.CONFIG_MISSING, {"element": "Thing", "option": "pull"})
    ]
