"""Compiling a project into a deployment package, and reading one back (decision 0024)."""

import json
from pathlib import PurePosixPath
from typing import cast

import pytest

from primum_core.compiler import compile_package
from primum_core.errors import CoreErrorCode
from primum_core.generated.model import Package, PackageSequence
from primum_core.package import canonical, package_hash, read_package
from project_builder import Ids, Project

LED, BUTTON, LAMP = 4, 5, 9
SHOW, DIM = 20, 30
TARGET, LEVEL = 31, 32
PATH = PurePosixPath("shop.package.json")


def _document(project: Project) -> dict[str, object]:
    compiled = compile_package(project.loaded())
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

    compiled = compile_package(project.loaded())

    assert compiled.value is None
    assert [(issue.code, dict(issue.params)) for issue in compiled.issues] == [
        (CoreErrorCode.PACKAGE_NO_BOARD, {})
    ]


def test_a_project_on_several_boards_cannot_be_built_yet(project: Project, ids: Ids) -> None:
    other = [{"id": ids(90), "name": "Other Pi", "model": "rpi4b"}]
    project.add("other.hw", "hardware", ids(91), boards=other, elements=[])

    compiled = compile_package(project.loaded())

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


def _rehashed(document: dict[str, object]) -> bytes:
    """The bytes of a package changed by hand, its hash made right again."""
    return json.dumps({**document, "hash": package_hash(document)}).encode()


def _full(project: Project, ids: Ids) -> dict[str, object]:
    """A package with a bit of everything: a command with an argument, an event, an
    automation that starts the sequence and sets a variable."""
    _names(_lamp(project, ids), ids)
    _show(project, ids, _clip(ids, 21, 0, 1000, "set", level={"valueOf": "brightness"}))
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
    project.add("go.auto", "automation", ids(71), name="Go", when=[ids(70)], do=do)
    return _document(project)


def _first(document: dict[str, object], *path: str | int) -> dict[str, object]:
    """The object at ``path`` inside the document, to change in place."""
    found: object = document
    for step in path:
        inside = cast("dict[str | int, object]", found)  # a list is indexed the same way
        found = inside[step]
    return cast("dict[str, object]", found)


COMMAND = ("sequences", 0, "commands", 0)
ARGUMENT = (*COMMAND, "arguments", 0)
START, SET = ("automations", 0, "do", 0), ("automations", 0, "do", 1)
UNKNOWN = "00000000-0000-0000-0000-000000000999"


@pytest.mark.parametrize(
    ("path", "change", "code", "pointer"),
    [
        (
            COMMAND,
            {"element": UNKNOWN},
            CoreErrorCode.REF_UNKNOWN,
            "/sequences/0/commands/0/element",
        ),
        (
            ARGUMENT,
            {"variable": UNKNOWN},
            CoreErrorCode.REF_UNKNOWN,
            "/sequences/0/commands/0/arguments/0/variable",
        ),
        (
            ARGUMENT,
            {"value": 3},
            CoreErrorCode.SCHEMA_UNEXPECTED_FIELD,
            "/sequences/0/commands/0/arguments/0/variable",
        ),
        (
            ARGUMENT,
            {"variable": None},
            CoreErrorCode.SCHEMA_MISSING_FIELD,
            "/sequences/0/commands/0/arguments/0",
        ),
        (
            COMMAND,
            {"atMs": 500, "untilMs": 400},
            CoreErrorCode.SCHEMA_INVALID_VALUE,
            "/sequences/0/commands/0/untilMs",
        ),
        (START, {"sequence": None}, CoreErrorCode.SCHEMA_MISSING_FIELD, "/automations/0/do/0"),
        (START, {"sequence": UNKNOWN}, CoreErrorCode.REF_UNKNOWN, "/automations/0/do/0/sequence"),
        (START, {"value": 1}, CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, "/automations/0/do/0/value"),
        (SET, {"variable": UNKNOWN}, CoreErrorCode.REF_UNKNOWN, "/automations/0/do/1/variable"),
        (SET, {"value": None}, CoreErrorCode.SCHEMA_MISSING_FIELD, "/automations/0/do/1"),
        (
            ("automations", 0),
            {"when": [UNKNOWN]},
            CoreErrorCode.REF_UNKNOWN,
            "/automations/0/when/0",
        ),
        (("events", 0), {"element": UNKNOWN}, CoreErrorCode.REF_UNKNOWN, "/events/0/element"),
        (("events", 0), {"element": None}, CoreErrorCode.SCHEMA_MISSING_FIELD, "/events/0"),
        (
            ("elements", 1),
            {"id": "00000000-0000-0000-0000-000000000004"},
            CoreErrorCode.ID_DUPLICATE,
            "/elements/1",
        ),
    ],
)
def test_a_package_that_does_not_hold_together_is_refused_whatever_its_hash(
    project: Project,
    ids: Ids,
    path: tuple[str | int, ...],
    change: dict[str, object],
    code: CoreErrorCode,
    pointer: str,
) -> None:
    document = _full(project, ids)
    target = _first(document, *path)
    for key, value in change.items():
        if value is None:
            del target[key]
        else:
            target[key] = value

    read = read_package(PATH, _rehashed(document))

    assert read.value is None
    found = [(issue.code, issue.location and issue.location.pointer) for issue in read.issues]
    assert (code, pointer) in found


@pytest.mark.parametrize(
    ("number", "written"),
    [
        (1e-05, "0.00001"),
        (1e-07, "1e-7"),
        (0.000001, "0.000001"),
        (1e21, "1e+21"),
        (1e20, "100000000000000000000"),
        (333333333.33333329, "333333333.3333333"),
        (4.5, "4.5"),
        (0.002, "0.002"),
        (1e-27, "1e-27"),
        (-0.0, "0"),
        (80.0, "80"),
        (-2.5, "-2.5"),
        (2**53 + 2, "9007199254740994"),
    ],
)
def test_numbers_are_written_for_the_hash_as_javascript_writes_them(
    number: float, written: str
) -> None:
    """RFC 8785: what ``JSON.stringify`` gives, so that the UI computes the same hash."""
    assert canonical({"n": number}) == '{"n":' + written + "}"


def test_the_canonical_form_sorts_keys_and_keeps_text_as_it_is() -> None:
    assert canonical({"b": [True, None, "año\n"], "a": {"d": 1, "c": "x"}}) == (
        '{"a":{"c":"x","d":1},"b":[true,null,"año\\n"]}'
    )


def test_a_package_with_half_a_character_is_refused_and_does_not_raise(project: Project) -> None:
    content = json.dumps(_document(project)).replace("Shop window", "Shop \\ud83d window")

    read = read_package(PATH, content.encode())

    assert read.value is None
    assert [issue.code for issue in read.issues] == [CoreErrorCode.FILE_INVALID_TEXT]


BRIGHTNESS = ("variables", 0)
LED_OPTIONS = ("elements", 1, "config")


@pytest.mark.parametrize(
    ("path", "change", "code", "pointer"),
    [
        (BRIGHTNESS, {"initial": 500}, CoreErrorCode.VARIABLE_INITIAL_OUT_OF_RANGE, "/variables/0"),
        (BRIGHTNESS, {"min": 200}, CoreErrorCode.VARIABLE_LIMITS_INVALID, "/variables/0"),
        (
            BRIGHTNESS,
            {"initial": "high"},
            CoreErrorCode.VALUE_EXPECTED_INTEGER,
            "/variables/0/initial",
        ),
        (
            BRIGHTNESS,
            {"type": "text", "initial": "a"},
            CoreErrorCode.SCHEMA_UNEXPECTED_FIELD,
            "/variables/0/min",
        ),
        (SET, {"value": 500}, CoreErrorCode.VARIABLE_SET_OUT_OF_RANGE, "/automations/0/do/1/value"),
        (SET, {"value": "high"}, CoreErrorCode.VALUE_EXPECTED_INTEGER, "/automations/0/do/1/value"),
        (
            COMMAND,
            {"atMs": 5000, "untilMs": 6000},
            CoreErrorCode.SCHEMA_INVALID_VALUE,
            "/sequences/0/commands/0/atMs",
        ),
        (
            COMMAND,
            {"untilMs": 6000},
            CoreErrorCode.SCHEMA_INVALID_VALUE,
            "/sequences/0/commands/0/untilMs",
        ),
    ],
)
def test_a_package_whose_values_do_not_fit_is_refused_whatever_its_hash(
    project: Project,
    ids: Ids,
    path: tuple[str | int, ...],
    change: dict[str, object],
    code: CoreErrorCode,
    pointer: str,
) -> None:
    document = _full(project, ids)
    _first(document, *path).update(change)

    read = read_package(PATH, _rehashed(document))

    assert read.value is None
    assert (code, pointer) in [
        (issue.code, issue.location and issue.location.pointer) for issue in read.issues
    ]


def test_a_package_that_increments_a_text_is_refused(project: Project, ids: Ids) -> None:
    document = _full(project, ids)
    _first(document, *BRIGHTNESS).update({"type": "text", "initial": "a"})
    for limit in ("min", "max"):
        del _first(document, *BRIGHTNESS)[limit]
    step = _first(document, *SET)
    step["action"] = "increment_variable"
    del step["value"]
    del _first(document, *ARGUMENT)["variable"]
    _first(document, *ARGUMENT)["value"] = 1

    read = read_package(PATH, _rehashed(document))

    assert [(issue.code, issue.location and issue.location.pointer) for issue in read.issues] == [
        (CoreErrorCode.VARIABLE_NOT_NUMERIC, "/automations/0/do/1/variable")
    ]


def test_a_package_that_gives_an_argument_or_an_option_twice_is_refused(
    project: Project, ids: Ids
) -> None:
    document = _full(project, ids)
    arguments = cast("list[object]", _first(document, *COMMAND)["arguments"])
    arguments.append({"name": "level", "value": 3})
    options = cast("list[object]", _first(document, "elements", 1)["config"])
    options.append(dict(cast("dict[str, object]", options[0])))

    read = read_package(PATH, _rehashed(document))

    assert [(issue.code, issue.location and issue.location.pointer) for issue in read.issues] == [
        (CoreErrorCode.CONFIG_DUPLICATE, "/elements/1/config/2"),
        (CoreErrorCode.ACTION_PARAM_DUPLICATE, "/sequences/0/commands/0/arguments/1"),
    ]


def test_keys_are_sorted_as_javascript_compares_text() -> None:
    """RFC 8785 sorts by UTF-16 units: a character beyond the basic plane (two units, the
    first 0xD83D) goes before one near its end (0xFB33), though its code point is higher."""
    assert canonical({"דּ": 1, "\U0001f600": 2, "a": 3}) == '{"a":3,"\U0001f600":2,"דּ":1}'


def test_a_project_is_compiled_with_the_drivers_it_was_checked_against(
    project: Project, ids: Ids
) -> None:
    _show(_lamp(project, ids), ids, _clip(ids, 21, 0, 1000, "set", level=40))
    workspace = project.loaded()
    project.drivers.clear()

    assert compile_package(workspace).value is not None
