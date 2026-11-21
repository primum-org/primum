"""Compiling a project into a deployment package, and reading one back (decision 0024)."""

import json
from pathlib import PurePosixPath
from typing import cast

from primum_core.compiler import compile_package
from primum_core.errors import CoreErrorCode
from primum_core.generated.model import Package, PackageSequence
from primum_core.package import package_hash, read_package
from project_builder import Ids, Project

LED, BUTTON, LAMP = 4, 5, 9
SHOW, DIM = 20, 30
TARGET, LEVEL = 31, 32
PATH = PurePosixPath("shop.package.json")


def _document(project: Project) -> dict[str, object]:
    compiled = compile_package(project.loaded(), project.drivers)
    assert compiled.value is not None, compiled.issues
    return compiled.value


def _package(project: Project) -> Package:
    """The package of the project, read back from the bytes that would be written."""
    read = read_package(PATH, json.dumps(_document(project)).encode())
    assert read.value is not None, read.issues
    return read.value


def _clip(
    ids: Ids, number: int, at_ms: int, duration_ms: int, action: str, **given: object
) -> dict[str, object]:
    arguments = [
        {"name": name.rstrip("_"), **(value if isinstance(value, dict) else {"value": value})}
        for name, value in given.items()
    ]
    clip: dict[str, object] = {"id": ids(number), "atMs": at_ms, "durationMs": duration_ms}
    return {**clip, "action": action, "arguments": arguments}


def _lamp(project: Project, ids: Ids, **fields: object) -> Project:
    lamp = {"id": ids(LAMP), "name": "Lamp", "board": ids(3), "type": "pwm_output", "pin": 18}
    return project.add("lamp.hw", "hardware", ids(8), boards=[], elements=[{**lamp, **fields}])


def _show(project: Project, ids: Ids, *clips: dict[str, object], **fields: object) -> Project:
    tracks = [{"element": ids(LAMP), "clips": list(clips)}]
    return project.add("show.sec", "sequence", ids(SHOW), name="Show", tracks=tracks, **fields)


def _only_sequence(package: Package) -> PackageSequence:
    [sequence] = package.sequences
    return sequence


def _commands(package: Package) -> list[tuple[str, int, int, int | None, dict[str, object]]]:
    """Each command of the only sequence: action, start, length, until and arguments."""
    return [
        (
            command.action,
            command.at_ms,
            command.duration_ms,
            command.until_ms,
            {
                argument.name: argument.value if argument.variable is None else argument.variable
                for argument in command.arguments
            },
        )
        for command in _only_sequence(package).commands
    ]


def test_a_package_says_its_project_its_board_and_its_elements(project: Project, ids: Ids) -> None:
    package = _package(project)

    assert (package.project.name, package.board.name, package.board.model) == (
        "Shop window",
        "Pi",
        "rpi4b",
    )
    assert [(element.name, element.type, element.pin) for element in package.elements] == [
        ("LED", "digital_output", 17),
        ("Button", "digital_input", 27),
    ]


def test_an_element_carries_every_option_of_its_driver(project: Project, ids: Ids) -> None:
    _lamp(project, ids)

    options = {
        element.name: {option.name: option.value for option in element.config}
        for element in _package(project).elements
    }

    assert options == {
        "LED": {},
        "Button": {"pull": "up", "debounceMs": 20},
        "Lamp": {"frequencyHz": 1000},
    }


def test_clips_become_commands_with_how_long_each_is_in_force(project: Project, ids: Ids) -> None:
    _lamp(project, ids)
    on, dim = _clip(ids, 21, 0, 0, "on"), _clip(ids, 22, 5000, 1000, "set", level=30)
    _show(project, ids, on, dim, _clip(ids, 23, 8000, 0, "off"), _clip(ids, 24, 8000, 1000, "on"))

    assert _commands(_package(project)) == [
        ("on", 0, 0, 8000, {}),  # until the next instant command of the lamp
        ("set", 5000, 1000, 6000, {"level": 30}),
        ("off", 8000, 0, 9000, {}),  # until the sequence ends
        ("on", 8000, 1000, 9000, {}),
    ]


def test_a_sequence_that_holds_keeps_its_last_commands_without_an_end(
    project: Project, ids: Ids
) -> None:
    _lamp(project, ids)
    fade = _clip(ids, 21, 0, 2000, "fade", from_=0, to=100)
    _show(project, ids, fade, whenDone="hold", whenStartedAgain="ignore", exclusiveGroup="lamp")

    sequence = _only_sequence(_package(project))

    assert (sequence.when_done, sequence.when_started_again, sequence.exclusive_group) == (
        "hold",
        "ignore",
        "lamp",
    )
    assert sequence.duration_ms == 2000
    assert _commands(_package(project)) == [("fade", 0, 2000, None, {"from": 0, "to": 100})]


def test_an_optional_parameter_left_out_is_left_out(project: Project, ids: Ids) -> None:
    _lamp(project, ids)
    _show(project, ids, _clip(ids, 21, 0, 2000, "fade", to=0))

    assert _commands(_package(project)) == [("fade", 0, 2000, 2000, {"to": 0})]


def _names(project: Project, ids: Ids) -> Project:
    constants = [{"id": ids(61), "name": "peak", "type": "number", "value": 80}]
    brightness = {"id": ids(62), "name": "brightness", "type": "integer", "initial": 50}
    variables = [{**brightness, "min": 0, "max": 100, "setting": True}]
    return project.add("shop.vars", "variables", ids(60), constants=constants, variables=variables)


def test_a_constant_is_put_in_place_and_a_variable_stays_a_reference(
    project: Project, ids: Ids
) -> None:
    _names(_lamp(project, ids), ids)
    to_peak = _clip(ids, 21, 0, 1000, "set", level={"valueOf": "peak"})
    to_brightness = _clip(ids, 22, 1000, 1000, "set", level={"valueOf": "brightness"})
    _show(project, ids, to_peak, to_brightness)

    package = _package(project)

    assert _commands(package) == [
        ("set", 0, 1000, 1000, {"level": 80}),
        ("set", 1000, 1000, 2000, {"level": package.variables[0].id}),
    ]
    assert [
        (v.name, v.type, v.initial, v.min, v.max, v.persistent, v.setting)
        for v in package.variables
    ] == [("brightness", "integer", 50, 0, 100, False, True)]


def _dim_included(project: Project, ids: Ids, **level: object) -> Project:
    """*Dim(target, level)* sets its target to its level; *Show* includes it on the lamp at
    2 s with the level given."""
    parameters = [
        {"id": ids(TARGET), "name": "target", "type": "element"},
        {"id": ids(LEVEL), "name": "level", "type": "number"},
    ]
    clip = _clip(ids, 33, 0, 1000, "set", level={"valueOf": "level"})
    tracks = [{"element": ids(TARGET), "clips": [clip]}]
    project.add("dim.sec", "sequence", ids(DIM), name="Dim", parameters=parameters, tracks=tracks)
    arguments = [
        {"parameter": ids(TARGET), "element": ids(LAMP)},
        {"parameter": ids(LEVEL), **level},
    ]
    block = {"id": ids(25), "sequence": ids(DIM), "atMs": 2000, "arguments": arguments}
    return project.add("show.sec", "sequence", ids(SHOW), name="Show", tracks=[], blocks=[block])


def test_a_component_is_expanded_into_the_sequence_that_includes_it(
    project: Project, ids: Ids
) -> None:
    _dim_included(_lamp(project, ids), ids, value=40)

    package = _package(project)

    assert [sequence.name for sequence in package.sequences] == ["Show"]
    assert _commands(package) == [("set", 2000, 1000, 3000, {"level": 40})]
    assert str(_only_sequence(package).commands[0].element) == ids(LAMP)


def test_a_variable_given_to_a_component_reaches_its_command(project: Project, ids: Ids) -> None:
    _names(_lamp(project, ids), ids)
    _dim_included(project, ids, valueOf="brightness")

    package = _package(project)

    assert _commands(package) == [("set", 2000, 1000, 3000, {"level": package.variables[0].id})]


def test_an_automation_names_its_variable_by_id(project: Project, ids: Ids) -> None:
    _names(_show(_lamp(project, ids), ids, _clip(ids, 21, 0, 1000, "on")), ids)
    project.add(
        "pressed.evt",
        "event",
        ids(70),
        name="Pressed",
        source="element",
        element=ids(BUTTON),
        trigger="on",
    )
    do = [
        {"action": "start_sequence", "sequence": ids(SHOW)},
        {"action": "set_variable", "variable": "brightness", "value": 30},
    ]
    automation = {"name": "Go", "when": [ids(70)], "if": "brightness < peak", "do": do}
    project.add("go.auto", "automation", ids(71), **automation)

    package = _package(project)
    [go] = package.automations

    assert (go.enabled, go.if_, [str(event) for event in go.when]) == (
        True,
        "brightness < peak",
        [ids(70)],
    )
    assert [(step.action, step.sequence, step.variable, step.value) for step in go.do] == [
        ("start_sequence", package.sequences[0].id, None, None),
        ("set_variable", None, package.variables[0].id, 30),
    ]
    assert [(event.source, str(event.element), event.trigger) for event in package.events] == [
        ("element", ids(BUTTON), "on")
    ]


def test_schedules_keep_their_times_and_windows(project: Project, ids: Ids) -> None:
    times = [{"days": ["mon"], "at": "08:00"}]
    windows = [{"days": ["sat", "sun"], "from": "19:00", "to": "23:00"}]
    project.add("open.sched", "schedule", ids(80), name="Open", times=times, windows=windows)

    [schedule] = _package(project).schedules

    assert [(time.days, time.at) for time in schedule.times] == [(("mon",), "08:00")]
    assert [(w.days, w.from_, w.to) for w in schedule.windows] == [
        (("sat", "sun"), "19:00", "23:00")
    ]


def test_the_same_project_gives_the_same_package_whatever_the_order_of_its_files(
    project: Project, ids: Ids
) -> None:
    _show(_lamp(project, ids), ids, _clip(ids, 21, 0, 1000, "on"))
    backwards = Project(dict(reversed(project.files.items())))

    assert _document(project) == _document(backwards)


def test_a_project_without_a_board_cannot_be_built(ids: Ids) -> None:
    project = Project().add("project.json", "project", ids(1), name="Empty")

    compiled = compile_package(project.loaded(), project.drivers)

    assert compiled.value is None
    assert [(issue.code, dict(issue.params)) for issue in compiled.issues] == [
        (CoreErrorCode.PACKAGE_NO_BOARD, {})
    ]


def test_a_project_on_several_boards_cannot_be_built_yet(project: Project, ids: Ids) -> None:
    other = [{"id": ids(90), "name": "Other Pi", "model": "rpi4b"}]
    project.add("other.hw", "hardware", ids(91), boards=other, elements=[])

    compiled = compile_package(project.loaded(), project.drivers)

    assert compiled.value is None
    assert [(issue.code, dict(issue.params)) for issue in compiled.issues] == [
        (CoreErrorCode.PACKAGE_SEVERAL_BOARDS, {"boards": ("Pi", "Other Pi")})
    ]


def test_a_package_carries_the_hash_of_the_rest_of_it(project: Project) -> None:
    document = _document(project)

    assert document["hash"] == package_hash(document)
    assert str(document["hash"]).startswith("sha256:")


def test_a_package_changed_after_it_was_built_is_refused(project: Project) -> None:
    document = _document(project)
    cast("dict[str, object]", document["project"])["name"] = "Another"

    read = read_package(PATH, json.dumps(document).encode())

    assert read.value is None
    assert [(issue.code, issue.location and issue.location.pointer) for issue in read.issues] == [
        (CoreErrorCode.PACKAGE_HASH_MISMATCH, "/hash")
    ]


def test_a_file_that_is_not_a_package_is_refused_by_its_shape(project: Project) -> None:
    document = {key: value for key, value in _document(project).items() if key != "sequences"}

    read = read_package(PATH, json.dumps(document).encode())

    assert read.value is None
    assert [issue.code for issue in read.issues] == [CoreErrorCode.SCHEMA_MISSING_FIELD]


def test_a_whole_number_hashes_the_same_however_it_is_written(project: Project) -> None:
    document = _document(project)
    rewritten = json.loads(
        json.dumps(document).replace('"schemaVersion": 1', '"schemaVersion": 1.0')
    )

    assert package_hash(rewritten) == document["hash"]
