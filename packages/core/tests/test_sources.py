"""Arguments that take their value from a name (``valueOf``, decision 0024): a constant, a
variable, or a value parameter of the sequence, given by the block that includes it."""

import pytest

from primum_core.errors import CoreErrorCode
from primum_core.generated.model import DriverParameter
from primum_core.given import limits_within, within
from project_builder import Found, Ids, Project

LAMP = 9
SHOW, DIM, OUTER = 20, 30, 40
TARGET, LEVEL, PASSED = 31, 32, 41  # parameters: of Dim, and of Outer


def _lamp(project: Project, ids: Ids) -> Project:
    lamp = {"id": ids(LAMP), "name": "Lamp", "board": ids(3), "type": "pwm_output", "pin": 18}
    return project.add("lamp.hw", "hardware", ids(8), boards=[], elements=[lamp])


def _names(project: Project, ids: Ids, **fields: object) -> Project:
    """A ``.vars`` file at the root: ``peak`` (a constant, 80) and ``brightness`` (a variable
    from 0 to 100), unless ``fields`` say otherwise."""
    constants = [{"id": ids(61), "name": "peak", "type": "number", "value": 80}]
    brightness = {"id": ids(62), "name": "brightness", "type": "integer", "initial": 50}
    variables = [{**brightness, "min": 0, "max": 100, "setting": True}]
    content = {"constants": constants, "variables": variables, "exports": ["peak"], **fields}
    return project.add("shop.vars", "variables", ids(60), **content)


def _set(ids: Ids, number: int, **argument: object) -> dict[str, object]:
    """A clip that sets the lamp's level to what ``argument`` says (``value`` or ``valueOf``)."""
    clip: dict[str, object] = {"id": ids(number), "atMs": 0, "durationMs": 1000, "action": "set"}
    return {**clip, "arguments": [{"name": "level", **argument}]}


def _show(project: Project, ids: Ids, **argument: object) -> Project:
    tracks = [{"element": ids(LAMP), "clips": [_set(ids, 21, **argument)]}]
    return project.add("show.sec", "sequence", ids(SHOW), name="Show", tracks=tracks)


def _dim(project: Project, ids: Ids, *, on: int = TARGET, level_type: str = "number") -> Project:
    """``Dim(target: element, level)``: sets ``target`` (or the lamp itself) to ``level``."""
    parameters = [
        {"id": ids(TARGET), "name": "target", "type": "element"},
        {"id": ids(LEVEL), "name": "level", "type": level_type},
    ]
    tracks = [{"element": ids(on), "clips": [_set(ids, 33, valueOf="level")]}]
    return project.add(
        "dim.sec", "sequence", ids(DIM), name="Dim", parameters=parameters, tracks=tracks
    )


def _including_dim(
    project: Project, ids: Ids, number: int = SHOW, name: str = "Show", **fields: object
) -> Project:
    """A sequence that includes *Dim* on the lamp, its level as ``fields`` say."""
    level = {key: fields.pop(key) for key in ("value", "valueOf") if key in fields}
    arguments = [
        {"parameter": ids(TARGET), "element": ids(LAMP)},
        {"parameter": ids(LEVEL), **level},
    ]
    block = {"id": ids(number + 5), "sequence": ids(DIM), "atMs": 0, "arguments": arguments}
    return project.add(
        f"{name.lower()}.sec",
        "sequence",
        ids(number),
        name=name,
        tracks=[],
        blocks=[block],
        **fields,
    )


def _asked(**params: object) -> dict[str, object]:
    return {"action": "set", "element": "Lamp", "parameter": "level", **params}


ARGUMENT = "/tracks/0/clips/0/arguments/0"


def test_a_clip_takes_the_value_of_a_constant(project: Project, ids: Ids) -> None:
    _names(_lamp(project, ids), ids)
    _show(project, ids, valueOf="peak")

    assert project.found() == []


def test_a_constant_is_checked_as_if_it_were_written(project: Project, ids: Ids) -> None:
    constants = [{"id": ids(61), "name": "peak", "type": "number", "value": 150}]
    _names(_lamp(project, ids), ids, constants=constants)
    _show(project, ids, valueOf="peak")

    assert project.found() == [
        (
            CoreErrorCode.ACTION_PARAM_OUT_OF_RANGE,
            _asked(min=0, max=100),
            "show.sec",
            f"{ARGUMENT}/valueOf",
        )
    ]


def test_a_constant_of_another_type_is_refused(project: Project, ids: Ids) -> None:
    constants = [{"id": ids(61), "name": "peak", "type": "text", "value": "high"}]
    _names(_lamp(project, ids), ids, constants=constants)
    _show(project, ids, valueOf="peak")

    assert project.found() == [
        (
            CoreErrorCode.VALUE_EXPECTED_NUMBER,
            {"field": "tracks[0].clips[0].arguments[0].valueOf"},
            "show.sec",
            f"{ARGUMENT}/valueOf",
        )
    ]


def test_a_clip_takes_the_value_of_a_variable_limited_within_the_parameter(
    project: Project, ids: Ids
) -> None:
    _names(_lamp(project, ids), ids)
    _show(project, ids, valueOf="brightness")

    assert project.found() == []


@pytest.mark.parametrize(
    "limits",
    [{}, {"min": 0}, {"max": 100}, {"min": -1, "max": 100}, {"min": 0, "max": 101}],
)
def test_a_variable_that_may_leave_the_limits_of_the_parameter_is_refused(
    project: Project, ids: Ids, limits: dict[str, int]
) -> None:
    variable = {"id": ids(62), "name": "brightness", "type": "integer", "initial": 50, **limits}
    _names(_lamp(project, ids), ids, variables=[{**variable, "setting": True}])
    _show(project, ids, valueOf="brightness")

    assert project.found() == [
        (
            CoreErrorCode.ACTION_PARAM_VARIABLE_UNLIMITED,
            _asked(name="brightness", min=0, max=100),
            "show.sec",
            f"{ARGUMENT}/valueOf",
        )
    ]


def test_a_variable_of_another_type_is_refused(project: Project, ids: Ids) -> None:
    variable = {"id": ids(62), "name": "brightness", "type": "boolean", "initial": True}
    _names(_lamp(project, ids), ids, variables=[{**variable, "setting": True}])
    _show(project, ids, valueOf="brightness")

    assert [code for code, *_ in project.found()] == [CoreErrorCode.VALUE_EXPECTED_NUMBER]


def test_a_name_that_stands_for_nothing_is_reported_once(project: Project, ids: Ids) -> None:
    _show(_lamp(project, ids), ids, valueOf="nothing")

    assert project.found() == [
        (CoreErrorCode.NAME_UNKNOWN, {"name": "nothing"}, "show.sec", f"{ARGUMENT}/valueOf")
    ]


def test_a_name_used_by_a_clip_is_used(project: Project, ids: Ids) -> None:
    variable = {"id": ids(62), "name": "brightness", "type": "integer", "initial": 50}
    limited = [{**variable, "min": 0, "max": 100}]
    _names(_lamp(project, ids), ids, variables=limited, exports=[])
    _show(project, ids, valueOf="brightness")

    assert project.found() == [
        (CoreErrorCode.NAME_UNUSED, {"name": "peak"}, "shop.vars", "/constants/0")
    ]


@pytest.mark.parametrize(
    ("argument", "code", "pointer"),
    [
        ({}, CoreErrorCode.SCHEMA_MISSING_FIELD, ARGUMENT),
        (
            {"value": 40, "valueOf": "peak"},
            CoreErrorCode.SCHEMA_UNEXPECTED_FIELD,
            f"{ARGUMENT}/valueOf",
        ),
    ],
)
def test_an_argument_is_a_value_or_the_name_of_one(
    project: Project, ids: Ids, argument: dict[str, object], code: CoreErrorCode, pointer: str
) -> None:
    _names(_lamp(project, ids), ids)
    _show(project, ids, **argument)

    assert [(found, at) for found, _, _, at in project.found() if found is code] == [
        (code, pointer)
    ]


def test_a_component_uses_its_value_parameter_and_a_block_gives_it(
    project: Project, ids: Ids
) -> None:
    _dim(_lamp(project, ids), ids)
    _including_dim(project, ids, value=40)

    assert project.found() == []


def test_an_element_parameter_is_not_a_value(project: Project, ids: Ids) -> None:
    _lamp(project, ids)
    parameters = [{"id": ids(TARGET), "name": "target", "type": "element"}]
    tracks = [{"element": ids(TARGET), "clips": [_set(ids, 33, valueOf="target")]}]
    project.add("dim.sec", "sequence", ids(DIM), name="Dim", parameters=parameters, tracks=tracks)

    assert project.found() == [
        (CoreErrorCode.NAME_NOT_A_VALUE, {"name": "target"}, "dim.sec", f"{ARGUMENT}/valueOf")
    ]


def test_a_parameter_of_another_type_is_refused_in_the_component_itself(
    project: Project, ids: Ids
) -> None:
    _dim(_lamp(project, ids), ids, on=LAMP, level_type="text")

    assert project.found() == [
        (
            CoreErrorCode.VALUE_EXPECTED_NUMBER,
            {"field": "tracks[0].clips[0].arguments[0].valueOf"},
            "dim.sec",
            f"{ARGUMENT}/valueOf",
        )
    ]


def _out_of_range_at_the_block(path: str = "show.sec") -> Found:
    return (CoreErrorCode.ACTION_PARAM_OUT_OF_RANGE, _asked(min=0, max=100), path, "/blocks/0")


@pytest.mark.parametrize("on", [TARGET, LAMP])
def test_a_value_the_action_does_not_take_is_reported_at_the_block_that_gives_it(
    project: Project, ids: Ids, on: int
) -> None:
    """Whether the block also gives the element or the component names it itself."""
    _dim(_lamp(project, ids), ids, on=on)
    _including_dim(project, ids, value=150)

    assert project.found() == [_out_of_range_at_the_block()]


def test_a_block_gives_a_parameter_the_value_of_a_variable(project: Project, ids: Ids) -> None:
    _names(_dim(_lamp(project, ids), ids), ids)
    _including_dim(project, ids, valueOf="brightness")

    assert project.found() == []


def test_a_variable_given_through_a_block_is_held_to_the_limits_of_the_action(
    project: Project, ids: Ids
) -> None:
    variable = {"id": ids(62), "name": "brightness", "type": "integer", "initial": 50}
    unlimited = [{**variable, "setting": True}]
    _names(_dim(_lamp(project, ids), ids), ids, exports=[], constants=[], variables=unlimited)
    _including_dim(project, ids, valueOf="brightness")

    assert project.found() == [
        (
            CoreErrorCode.ACTION_PARAM_VARIABLE_UNLIMITED,
            _asked(name="brightness", min=0, max=100),
            "show.sec",
            "/blocks/0",
        )
    ]


def test_a_block_gives_a_name_of_the_type_of_the_parameter(project: Project, ids: Ids) -> None:
    constants = [{"id": ids(61), "name": "peak", "type": "text", "value": "high"}]
    _names(_dim(_lamp(project, ids), ids), ids, constants=constants)
    _including_dim(project, ids, valueOf="peak")

    assert project.found() == [
        (
            CoreErrorCode.VALUE_EXPECTED_NUMBER,
            {"field": "blocks[0].arguments[1].valueOf"},
            "show.sec",
            "/blocks/0/arguments/1/valueOf",
        )
    ]


def _outer_passing_its_parameter(project: Project, ids: Ids, value: int) -> Project:
    """*Outer(passed)* includes *Dim* with ``level = passed``; *Show* includes *Outer*."""
    passed = [{"id": ids(PASSED), "name": "passed", "type": "number"}]
    _including_dim(project, ids, OUTER, "Outer", valueOf="passed", parameters=passed)
    argument = {"parameter": ids(PASSED), "value": value}
    block = {"id": ids(25), "sequence": ids(OUTER), "atMs": 0, "arguments": [argument]}
    return project.add("show.sec", "sequence", ids(SHOW), name="Show", tracks=[], blocks=[block])


def test_a_parameter_is_passed_on_to_a_component_inside(project: Project, ids: Ids) -> None:
    _dim(_lamp(project, ids), ids)
    _outer_passing_its_parameter(project, ids, 40)

    assert project.found() == []


def test_a_value_passed_on_is_checked_where_it_is_finally_given(project: Project, ids: Ids) -> None:
    _dim(_lamp(project, ids), ids)
    _outer_passing_its_parameter(project, ids, 150)

    assert project.found() == [_out_of_range_at_the_block()]


def test_what_a_component_writes_wrong_is_reported_in_it_and_not_where_it_is_included(
    project: Project, ids: Ids
) -> None:
    _lamp(project, ids)
    tracks = [{"element": ids(LAMP), "clips": [_set(ids, 33, value=150)]}]
    project.add("dim.sec", "sequence", ids(DIM), name="Dim", tracks=tracks)
    block = {"id": ids(25), "sequence": ids(DIM), "atMs": 0}
    project.add("show.sec", "sequence", ids(SHOW), name="Show", tracks=[], blocks=[block])

    assert [(code, path) for code, _, path, _ in project.found()] == [
        (CoreErrorCode.ACTION_PARAM_OUT_OF_RANGE, "dim.sec")
    ]


@pytest.mark.parametrize("action", ["start_sequence", "stop_sequence"])
def test_an_automation_cannot_start_or_stop_a_component(
    project: Project, ids: Ids, action: str
) -> None:
    _dim(_lamp(project, ids), ids)
    _including_dim(project, ids, value=40)
    project.add("pressed.evt", "event", ids(70), name="Pressed", source="ui")
    do = [{"action": action, "sequence": ids(DIM)}]
    project.add("go.auto", "automation", ids(71), name="Go", when=[ids(70)], do=do)

    assert project.found() == [
        (
            CoreErrorCode.AUTOMATION_STARTS_COMPONENT,
            {"sequence": "Dim"},
            "go.auto",
            "/do/0/sequence",
        )
    ]


@pytest.mark.parametrize(
    ("limits", "inside", "outside", "fitting", "too_wide"),
    [
        ({"max": 10}, -500, 11, (None, 10), (0, 11)),
        ({"min": 0}, 500, -1, (0, None), (-1, 10)),
        ({"min": 0, "max": 10}, 5, 11, (0, 10), (0, None)),
    ],
)
def test_a_limit_on_one_side_alone_still_limits(
    limits: dict[str, float],
    inside: float,
    outside: float,
    fitting: tuple[float | None, float | None],
    too_wide: tuple[float | None, float | None],
) -> None:
    """Manifests give both limits or neither, but nothing here should count on that."""
    low, high = limits.get("min"), limits.get("max")
    parameter = DriverParameter(name="level", type="number", min=low, max=high)

    assert within(inside, parameter)
    assert not within(outside, parameter)
    assert limits_within(*fitting, parameter)
    assert not limits_within(*too_wide, parameter)
    assert not limits_within(None, None, parameter)
