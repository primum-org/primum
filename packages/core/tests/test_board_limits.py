"""The options of each element, against the limits of its board."""

from dataclasses import replace

import pytest

from primum_core.errors import CoreErrorCode
from primum_core.generated.model import OptionLimit
from project_builder import PROFILES, Ids, Project, driver

BOARD = 3
FREQUENCY: dict[str, object] = {"name": "frequencyHz", "type": "integer"}


def _lamp(project: Project, ids: Ids, board: int = BOARD, **options: object) -> Project:
    lamp: dict[str, object] = {"id": ids(9), "name": "Lamp", "board": ids(board), "pin": 18}
    lamp["type"] = "pwm_output"
    if options:
        lamp["config"] = [{"name": name, "value": value} for name, value in options.items()]
    return project.add("lamp.hw", "hardware", ids(8), boards=[], elements=[lamp])


def _out_of_range(pointer: str) -> tuple[CoreErrorCode, dict[str, object], str, str]:
    params: dict[str, object] = {"element": "Lamp", "option": "frequencyHz", "board": "Pi"}
    params.update(min=1, max=100_000)
    return (CoreErrorCode.CONFIG_OUT_OF_BOARD_RANGE, params, "lamp.hw", pointer)


@pytest.mark.parametrize("frequency", [1, 1000, 100_000])
def test_a_frequency_the_board_takes(project: Project, ids: Ids, frequency: int) -> None:
    _lamp(project, ids, frequencyHz=frequency)

    assert project.found() == []


@pytest.mark.parametrize("frequency", [-50, 0, 100_001, 20_000_000])
def test_a_frequency_the_board_does_not_take(project: Project, ids: Ids, frequency: int) -> None:
    _lamp(project, ids, frequencyHz=frequency)

    assert project.found() == [_out_of_range("/elements/0/config/0/value")]


def test_the_default_of_the_driver_is_one_the_shipped_board_takes(
    project: Project, ids: Ids
) -> None:
    _lamp(project, ids)

    assert project.found() == []


def test_a_default_the_board_does_not_take_is_reported_at_the_element(
    project: Project, ids: Ids
) -> None:
    project.drivers["pwm_output"] = driver("pwm_output", config=[{**FREQUENCY, "default": 0}])
    _lamp(project, ids)

    assert project.found() == [_out_of_range("/elements/0")]


def test_an_option_without_a_default_that_is_not_given_is_only_missing(
    project: Project, ids: Ids
) -> None:
    project.drivers["pwm_output"] = driver("pwm_output", config=[FREQUENCY])
    _lamp(project, ids)

    assert [code for code, *_ in project.found()] == [CoreErrorCode.CONFIG_MISSING]


def test_a_value_of_another_type_is_only_that_problem(project: Project, ids: Ids) -> None:
    _lamp(project, ids, frequencyHz="fast")

    assert [code for code, *_ in project.found()] == [CoreErrorCode.VALUE_EXPECTED_INTEGER]


def test_an_option_given_twice_is_only_that_problem(project: Project, ids: Ids) -> None:
    lamp: dict[str, object] = {"id": ids(9), "name": "Lamp", "board": ids(BOARD), "pin": 18}
    lamp["type"] = "pwm_output"
    lamp["config"] = [{"name": "frequencyHz", "value": 0}, {"name": "frequencyHz", "value": 0}]
    project.add("lamp.hw", "hardware", ids(8), boards=[], elements=[lamp])

    assert [code for code, *_ in project.found()] == [CoreErrorCode.CONFIG_DUPLICATE]


def test_the_driver_keeps_its_own_limits_on_every_board(project: Project, ids: Ids) -> None:
    limited = {**FREQUENCY, "min": 100, "max": 200, "default": 150}
    project.drivers["pwm_output"] = driver("pwm_output", config=[limited])
    _lamp(project, ids, frequencyHz=50)

    assert [code for code, *_ in project.found()] == [CoreErrorCode.CONFIG_OUT_OF_RANGE]


def test_an_element_on_a_board_without_a_profile_is_not_checked(project: Project, ids: Ids) -> None:
    unknown = {"id": ids(7), "name": "Other", "model": "unknown-board"}
    lamp: dict[str, object] = {"id": ids(9), "name": "Lamp", "board": ids(7), "pin": 18}
    lamp["type"] = "pwm_output"
    lamp["config"] = [{"name": "frequencyHz", "value": 0}]
    project.add("lamp.hw", "hardware", ids(8), boards=[unknown], elements=[lamp])

    assert [code for code, *_ in project.found()] == [CoreErrorCode.BOARD_UNKNOWN_MODEL]


def test_a_limit_is_of_one_element_type(project: Project, ids: Ids) -> None:
    project.drivers["digital_output"] = driver(
        "digital_output", config=[{**FREQUENCY, "default": 0}]
    )

    assert project.found() == []


def test_each_limit_of_a_type_is_reported_at_its_own_place(project: Project, ids: Ids) -> None:
    """Two limits on PWM outputs: the frequency, given, and a dead time left to a default
    the board does not take. The second is at the element, not where the first was."""
    dead_time = {"name": "deadTimeNs", "type": "integer", "default": 0}
    project.drivers["pwm_output"] = driver("pwm_output", config=[FREQUENCY, dead_time])
    rpi4b = PROFILES["rpi4b"]
    source = ("https://example.org/datasheet.pdf",)
    second = OptionLimit(
        element_type="pwm_output", option="deadTimeNs", min=10, max=20, sources=source
    )
    project.profiles["rpi4b"] = replace(rpi4b, limits=(*rpi4b.limits, second))
    _lamp(project, ids, frequencyHz=0)

    assert [(params["option"], pointer) for _, params, _, pointer in project.found()] == [
        ("frequencyHz", "/elements/0/config/0/value"),
        ("deadTimeNs", "/elements/0"),
    ]
