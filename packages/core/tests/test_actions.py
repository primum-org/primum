"""What clips ask of their elements, against the manifest of each element's driver."""

import pytest

from primum_core.errors import CoreErrorCode
from project_builder import Ids, Project, driver

LED, BUTTON, LAMP = 4, 5, 9
FADE = 30  # a component: fades its `target`


def _clip(ids: Ids, number: int, action: str, **arguments: object) -> dict[str, object]:
    clip: dict[str, object] = {"id": ids(number), "atMs": number * 1000, "durationMs": 500}
    clip["action"] = action
    if arguments:
        clip["arguments"] = [{"name": name, "value": value} for name, value in arguments.items()]
    return clip


def _with_lamp(project: Project, ids: Ids) -> Project:
    """A PWM lamp on the same Pi: an element that takes actions with parameters."""
    lamp = {"id": ids(LAMP), "name": "Lamp", "board": ids(3), "type": "pwm_output", "pin": 18}
    return project.add("lamp.hw", "hardware", ids(8), boards=[], elements=[lamp])


def _show(project: Project, ids: Ids, element: int, *clips: dict[str, object]) -> Project:
    tracks = [{"element": ids(element), "clips": list(clips)}]
    return project.add("show.sec", "sequence", ids(20), name="Show", tracks=tracks)


def _fade_component(project: Project, ids: Ids, *clips: dict[str, object]) -> Project:
    return project.add(
        "fade.sec",
        "sequence",
        ids(FADE),
        name="Fade",
        parameters=[{"id": ids(31), "name": "target", "type": "element"}],
        tracks=[{"element": ids(31), "clips": list(clips)}],
    )


def _including_fade(project: Project, ids: Ids, element: int) -> Project:
    argument = {"parameter": ids(31), "element": ids(element)}
    block = {"id": ids(41), "sequence": ids(FADE), "atMs": 0, "arguments": [argument]}
    return project.add("show.sec", "sequence", ids(40), name="Show", tracks=[], blocks=[block])


def test_actions_of_the_driver_with_their_arguments_are_valid(project: Project, ids: Ids) -> None:
    _with_lamp(project, ids)
    _show(
        project,
        ids,
        LAMP,
        _clip(ids, 21, "on"),
        _clip(ids, 22, "set", level=40),
        _clip(ids, 23, "fade", **{"from": 0, "to": 100}),
        _clip(ids, 24, "off"),
    )

    assert project.found() == []


def test_an_action_the_driver_does_not_have(project: Project, ids: Ids) -> None:
    _show(project, ids, LED, _clip(ids, 21, "fade"))

    assert project.found() == [
        (
            CoreErrorCode.ACTION_UNKNOWN,
            {"action": "fade", "element": "LED", "available": ("on", "off")},
            "show.sec",
            "/tracks/0/clips/0/action",
        )
    ]


def test_a_track_on_an_input_is_an_error_even_without_clips(project: Project, ids: Ids) -> None:
    _show(project, ids, BUTTON)

    assert project.found() == [
        (
            CoreErrorCode.TRACK_ELEMENT_WITHOUT_ACTIONS,
            {"element": "Button"},
            "show.sec",
            "/tracks/0/element",
        )
    ]


def test_a_track_on_an_element_whose_type_has_no_driver(project: Project, ids: Ids) -> None:
    project.drivers.pop("digital_output")
    _show(project, ids, LED, _clip(ids, 21, "on"))

    assert [code for code, *_ in project.found()] == [CoreErrorCode.TRACK_ELEMENT_WITHOUT_ACTIONS]


@pytest.mark.parametrize(
    ("arguments", "code", "params", "pointer"),
    [
        (
            {},
            CoreErrorCode.ACTION_PARAM_MISSING,
            {"parameter": "level"},
            "/tracks/0/clips/0",
        ),
        (
            {"level": 150},
            CoreErrorCode.ACTION_PARAM_OUT_OF_RANGE,
            {"parameter": "level", "min": 0, "max": 100},
            "/tracks/0/clips/0/arguments/0/value",
        ),
        (
            {"level": 40, "speed": 2},
            CoreErrorCode.ACTION_PARAM_UNKNOWN,
            {"parameter": "speed"},
            "/tracks/0/clips/0/arguments/1",
        ),
    ],
)
def test_an_argument_that_does_not_fit_the_action(
    project: Project,
    ids: Ids,
    arguments: dict[str, object],
    code: CoreErrorCode,
    params: dict[str, object],
    pointer: str,
) -> None:
    _with_lamp(project, ids)
    _show(project, ids, LAMP, _clip(ids, 21, "set", **arguments))

    context = {"action": "set", "element": "Lamp"}
    assert project.found() == [(code, {**context, **params}, "show.sec", pointer)]


def test_an_argument_given_twice(project: Project, ids: Ids) -> None:
    _with_lamp(project, ids)
    clip = _clip(ids, 21, "set")
    clip["arguments"] = [{"name": "level", "value": 10}, {"name": "level", "value": 20}]
    _show(project, ids, LAMP, clip)

    assert [(code, pointer) for code, _, _, pointer in project.found()] == [
        (CoreErrorCode.ACTION_PARAM_DUPLICATE, "/tracks/0/clips/0/arguments/1")
    ]


def test_an_argument_of_another_type(project: Project, ids: Ids) -> None:
    _with_lamp(project, ids)
    _show(project, ids, LAMP, _clip(ids, 21, "set", level="half"))

    assert project.found() == [
        (
            CoreErrorCode.VALUE_EXPECTED_NUMBER,
            {"field": "tracks[0].clips[0].arguments[0].value"},
            "show.sec",
            "/tracks/0/clips/0/arguments/0/value",
        )
    ]


def test_an_argument_that_is_not_one_of_the_choices(project: Project, ids: Ids) -> None:
    direction: dict[str, object] = {"name": "direction", "type": "text"}
    direction["choices"] = ["up", "down"]
    off: dict[str, object] = {"name": "off", "parameters": []}
    actions = [off, {"name": "on", "parameters": [direction]}]
    project.drivers["digital_output"] = driver("digital_output", actions=actions, safeState="off")
    _show(project, ids, LED, _clip(ids, 21, "on", direction="sideways"))

    assert project.found() == [
        (
            CoreErrorCode.ACTION_PARAM_NOT_ALLOWED,
            {
                "action": "on",
                "element": "LED",
                "parameter": "direction",
                "allowed": ("up", "down"),
            },
            "show.sec",
            "/tracks/0/clips/0/arguments/0/value",
        )
    ]


def test_a_component_is_checked_where_a_block_gives_it_an_element(
    project: Project, ids: Ids
) -> None:
    _fade_component(project, ids, _clip(ids, 32, "fade", **{"from": 0, "to": 100}))
    _including_fade(project, ids, LED)  # a digital output cannot fade

    assert project.found() == [
        (
            CoreErrorCode.ACTION_UNKNOWN,
            {"action": "fade", "element": "LED", "available": ("on", "off")},
            "show.sec",
            "/blocks/0",
        )
    ]


def test_a_component_given_an_element_that_can_do_what_it_asks(project: Project, ids: Ids) -> None:
    _with_lamp(project, ids)
    _fade_component(project, ids, _clip(ids, 32, "fade", **{"from": 0, "to": 100}))
    _including_fade(project, ids, LAMP)

    assert project.found() == []


def test_a_component_nobody_includes_is_not_checked(project: Project, ids: Ids) -> None:
    _fade_component(project, ids, _clip(ids, 32, "no_such_action"))

    assert project.found() == []


def test_many_clips_with_the_same_problem_are_one_issue_per_block(
    project: Project, ids: Ids
) -> None:
    fades = [_clip(ids, number, "fade", **{"from": 0, "to": 100}) for number in (32, 33, 34)]
    _fade_component(project, ids, *fades)
    _including_fade(project, ids, LED)

    assert [(code, pointer) for code, _, _, pointer in project.found()] == [
        (CoreErrorCode.ACTION_UNKNOWN, "/blocks/0")
    ]


def test_a_component_given_an_input_is_an_error_at_the_block(project: Project, ids: Ids) -> None:
    _fade_component(project, ids, _clip(ids, 32, "on"))
    _including_fade(project, ids, BUTTON)

    assert project.found() == [
        (
            CoreErrorCode.TRACK_ELEMENT_WITHOUT_ACTIONS,
            {"element": "Button"},
            "show.sec",
            "/blocks/0",
        )
    ]


def test_an_argument_out_of_range_in_a_component_names_the_action_and_the_parameter(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    _fade_component(project, ids, _clip(ids, 32, "set", level=150))
    _including_fade(project, ids, LAMP)

    assert project.found() == [
        (
            CoreErrorCode.ACTION_PARAM_OUT_OF_RANGE,
            {"action": "set", "element": "Lamp", "parameter": "level", "min": 0, "max": 100},
            "show.sec",
            "/blocks/0",
        )
    ]


def test_a_parameter_passed_on_to_an_inner_component_is_checked_where_it_gets_its_element(
    project: Project, ids: Ids
) -> None:
    _fade_component(project, ids, _clip(ids, 32, "fade", **{"from": 0, "to": 100}))
    # Twice: a component with its own parameter, which it hands to Fade.
    inner = {"parameter": ids(31), "element": ids(51)}
    project.add(
        "twice.sec",
        "sequence",
        ids(50),
        name="Twice",
        parameters=[{"id": ids(51), "name": "what", "type": "element"}],
        tracks=[],
        blocks=[{"id": ids(52), "sequence": ids(FADE), "atMs": 0, "arguments": [inner]}],
    )
    outer = {"parameter": ids(51), "element": ids(LED)}
    block = {"id": ids(61), "sequence": ids(50), "atMs": 0, "arguments": [outer]}
    project.add("show.sec", "sequence", ids(60), name="Show", tracks=[], blocks=[block])

    assert [(code, path, pointer) for code, _, path, pointer in project.found()] == [
        (CoreErrorCode.ACTION_UNKNOWN, "show.sec", "/blocks/0")
    ]
