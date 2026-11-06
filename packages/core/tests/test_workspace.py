"""Loading a project: files by extension, unique ids, references by kind, fields by case."""

import json
from collections.abc import Mapping
from pathlib import PurePosixPath
from uuid import UUID

import pytest

from primum_core.errors import CoreErrorCode, Severity
from primum_core.workspace import MANIFEST, load_workspace
from project_builder import PROFILES

type Files = dict[PurePosixPath, bytes]
type Found = list[tuple[CoreErrorCode, dict[str, object], str, str]]


def _id(number: int) -> str:
    return str(UUID(int=number))


PROJECT, HARDWARE, BOARD, LED, BUTTON = (_id(n) for n in range(1, 6))
BLINK, CLIP, PRESSED, EVENING, GREET, VARS, COUNT = (_id(n) for n in range(6, 13))


def _file(kind: str, id_: str, **fields: object) -> bytes:
    return json.dumps({"id": id_, "kind": kind, "schemaVersion": 1, **fields}).encode()


def _project(**changes: Mapping[str, object]) -> Files:
    """A small valid project; ``changes`` replaces a file's fields by its path."""
    contents: dict[str, tuple[str, str, dict[str, object]]] = {
        "project.json": ("project", PROJECT, {"name": "Shop window"}),
        "hardware.hw": (
            "hardware",
            HARDWARE,
            {
                "boards": [{"id": BOARD, "name": "Pi", "model": "rpi4b"}],
                "elements": [
                    {"id": LED, "name": "LED", "board": BOARD, "type": "digital_output", "pin": 17},
                    {
                        "id": BUTTON,
                        "name": "Button",
                        "board": BOARD,
                        "type": "digital_input",
                        "pin": 27,
                    },
                ],
            },
        ),
        "scenes/blink.sec": (
            "sequence",
            BLINK,
            {
                "name": "Blink",
                "tracks": [
                    {
                        "element": LED,
                        "clips": [{"id": CLIP, "atMs": 0, "durationMs": 500, "action": "on"}],
                    }
                ],
            },
        ),
        "pressed.evt": (
            "event",
            PRESSED,
            {"name": "Pressed", "source": "element", "element": BUTTON, "trigger": "on"},
        ),
        "evening.sched": (
            "schedule",
            EVENING,
            {"name": "Evening", "times": [{"days": ["mon", "fri"], "at": "20:30"}]},
        ),
        "greet.auto": (
            "automation",
            GREET,
            {
                "name": "Greet",
                "when": [PRESSED, EVENING],
                "do": [
                    {"action": "start_sequence", "sequence": BLINK},
                    {"action": "increment_variable", "variable": "visits"},
                ],
            },
        ),
        "shop.vars": (
            "variables",
            VARS,
            {
                "constants": [],
                "variables": [{"id": COUNT, "name": "visits", "type": "integer", "initial": 0}],
            },
        ),
    }
    files: Files = {}
    for path, (kind, id_, fields) in contents.items():
        files[PurePosixPath(path)] = _file(kind, id_, **{**fields, **changes.get(path, {})})
    return files


def _found(files: Files) -> Found:
    return [
        (
            issue.code,
            dict(issue.params),
            str(issue.location.path) if issue.location else "",
            issue.location.pointer if issue.location else "",
        )
        for issue in load_workspace(files, PROFILES).issues
    ]


def test_a_valid_project_loads_with_every_file_by_path() -> None:
    parsed = load_workspace(_project(), PROFILES)

    assert parsed.issues == ()
    assert parsed.value is not None
    assert parsed.value.manifest.name == "Shop window"
    assert [str(file.path) for file in parsed.value.files] == [
        "evening.sched",
        "greet.auto",
        "hardware.hw",
        "pressed.evt",
        "scenes/blink.sec",
        "shop.vars",
    ]


def test_without_a_manifest_it_is_not_a_project() -> None:
    files = _project()
    del files[MANIFEST]

    parsed = load_workspace(files, PROFILES)

    assert parsed.value is None
    assert _found(files) == [(CoreErrorCode.PROJECT_MANIFEST_MISSING, {}, "project.json", "")]


def test_a_file_of_no_project_type_is_ignored_with_a_warning() -> None:
    files = _project()
    files[PurePosixPath("notes/README.md")] = b"# notes"

    parsed = load_workspace(files, PROFILES)

    assert parsed.value is not None
    [issue] = parsed.issues
    assert (issue.code, issue.severity) == (CoreErrorCode.FILE_NOT_IN_FORMAT, Severity.WARNING)


def test_a_file_is_read_by_the_format_of_its_extension() -> None:
    files = _project()
    files[PurePosixPath("hardware.hw")] = _file("sequence", HARDWARE, name="x", tracks=[])

    assert (
        CoreErrorCode.SCHEMA_NOT_ALLOWED,
        {"field": "kind", "allowed": ("hardware",)},
        "hardware.hw",
        "/kind",
    ) in _found(files)


def test_references_are_checked_only_once_every_file_reads() -> None:
    files = _project()
    files[PurePosixPath("hardware.hw")] = b"{"

    # Without the hardware file, the LED and the button do not exist: that is not reported.
    assert [code for code, *_ in _found(files)] == [CoreErrorCode.FILE_INVALID_JSON]


def test_an_id_used_twice_is_reported_at_the_second_file_by_path() -> None:
    files = _project(**{"pressed.evt": {"id": BLINK}})

    duplicates = [found for found in _found(files) if found[0] is CoreErrorCode.ID_DUPLICATE]
    assert duplicates == [(CoreErrorCode.ID_DUPLICATE, {"id": BLINK}, "scenes/blink.sec", "")]


def test_an_id_inside_a_file_must_be_unique_too() -> None:
    elements = json.loads(_project()[PurePosixPath("hardware.hw")])["elements"]
    elements.append({**elements[0], "pin": 22})
    files = _project(**{"hardware.hw": {"elements": elements}})

    assert _found(files) == [
        (CoreErrorCode.ID_DUPLICATE, {"id": LED}, "hardware.hw", "/elements/2")
    ]


def test_a_reference_to_nothing_is_reported_at_the_field() -> None:
    files = _project(**{"pressed.evt": {"element": _id(99)}})

    assert _found(files) == [
        (CoreErrorCode.REF_UNKNOWN, {"field": "element", "id": _id(99)}, "pressed.evt", "/element")
    ]


@pytest.mark.parametrize(
    ("path", "change", "field", "pointer"),
    [
        (
            "greet.auto",
            {
                "do": [
                    {"action": "start_sequence", "sequence": PRESSED},
                    {"action": "increment_variable", "variable": "visits"},
                ]
            },
            "do[0].sequence",
            "/do/0/sequence",
        ),
        ("greet.auto", {"when": [BLINK]}, "when[0]", "/when/0"),
        ("pressed.evt", {"element": BOARD}, "element", "/element"),
    ],
)
def test_a_reference_to_something_of_another_kind_is_reported(
    path: str, change: dict[str, object], field: str, pointer: str
) -> None:
    [(code, params, found_path, found_pointer)] = _found(_project(**{path: change}))

    assert (code, params["field"], found_path, found_pointer) == (
        CoreErrorCode.REF_WRONG_KIND,
        field,
        path,
        pointer,
    )


def test_a_component_plays_its_own_element_parameter() -> None:
    parameter = _id(50)
    blink: dict[str, object] = {
        "parameters": [{"id": parameter, "name": "target", "type": "element"}],
        "tracks": [{"element": parameter, "clips": []}],
    }

    assert _found(_project(**{"scenes/blink.sec": blink})) == []


def test_a_track_cannot_play_a_parameter_of_another_sequence() -> None:
    parameter = _id(50)
    files = _project(
        **{
            "scenes/blink.sec": {
                "parameters": [{"id": parameter, "name": "target", "type": "element"}]
            }
        }
    )
    track: dict[str, object] = {"element": parameter, "clips": []}
    files[PurePosixPath("other.sec")] = _file("sequence", _id(51), name="Other", tracks=[track])

    [(code, params, path, _)] = _found(files)
    assert (code, params["field"], path) == (
        CoreErrorCode.REF_WRONG_KIND,
        "tracks[0].element",
        "other.sec",
    )


def test_a_block_gives_arguments_only_to_parameters_of_the_sequence_it_includes() -> None:
    own_parameter = _id(50)
    blink = {"parameters": [{"id": own_parameter, "name": "target", "type": "element"}]}
    files = _project(**{"scenes/blink.sec": blink})
    files[PurePosixPath("show.sec")] = _file(
        "sequence",
        _id(51),
        name="Show",
        tracks=[],
        blocks=[
            {
                "id": _id(52),
                "sequence": BLINK,
                "atMs": 0,
                "arguments": [{"parameter": own_parameter, "element": LED}],
            },
            {
                "id": _id(53),
                "sequence": GREET,
                "atMs": 0,
                "arguments": [{"parameter": own_parameter, "element": LED}],
            },
        ],
    )

    assert [(code, params["field"]) for code, params, *_ in _found(files)] == [
        (CoreErrorCode.REF_WRONG_KIND, "blocks[1].sequence"),
        (CoreErrorCode.REF_WRONG_KIND, "blocks[1].arguments[0].parameter"),
    ]


@pytest.mark.parametrize(
    ("path", "change", "expected"),
    [
        (
            "hardware.hw",
            {"elements": [{"id": LED, "name": "LED", "board": BOARD, "type": "digital_output"}]},
            (CoreErrorCode.SCHEMA_MISSING_FIELD, "elements[0].pin", "/elements/0"),
        ),
        (
            "hardware.hw",
            {
                "elements": [
                    {
                        "id": LED,
                        "name": "IO",
                        "board": BOARD,
                        "type": "i2c_device",
                        "bus": "i2c1",
                        "address": 32,
                        "pin": 2,
                    }
                ]
            },
            (CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, "elements[0].pin", "/elements/0/pin"),
        ),
        (
            "pressed.evt",
            {"source": "ui"},
            (CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, "element", "/element"),
        ),
        (
            "greet.auto",
            {"do": [{"action": "set_variable", "variable": "visits"}]},
            (CoreErrorCode.SCHEMA_MISSING_FIELD, "do[0].value", "/do/0"),
        ),
    ],
)
def test_fields_that_depend_on_the_case_are_checked(
    path: str, change: dict[str, object], expected: tuple[CoreErrorCode, str, str]
) -> None:
    found = [
        (code, params["field"], pointer)
        for code, params, _, pointer in _found(_project(**{path: change}))
    ]

    assert expected in found


def test_a_track_plays_an_element_parameter_never_a_parameter_of_another_type() -> None:
    parameter = _id(50)
    blink: dict[str, object] = {
        "parameters": [{"id": parameter, "name": "times", "type": "number"}],
        "tracks": [{"element": parameter, "clips": []}],
    }

    [(code, params, _, pointer)] = _found(_project(**{"scenes/blink.sec": blink}))
    assert (code, params["field"], pointer) == (
        CoreErrorCode.REF_WRONG_KIND,
        "tracks[0].element",
        "/tracks/0/element",
    )


def test_an_event_comes_from_an_input_element_never_an_output() -> None:
    [(code, params, _, _)] = _found(_project(**{"pressed.evt": {"element": LED}}))

    assert (code, params["field"]) == (CoreErrorCode.REF_WRONG_KIND, "element")


def test_extensions_are_matched_without_regard_to_case() -> None:
    files = _project()
    files[PurePosixPath("SCENES/OTHER.SEC")] = _file("sequence", _id(60), name="Other", tracks=[])

    parsed = load_workspace(files, PROFILES)

    assert parsed.issues == ()
    assert parsed.value is not None
    assert PurePosixPath("SCENES/OTHER.SEC") in {file.path for file in parsed.value.files}


def test_fields_of_a_file_are_checked_even_if_another_file_does_not_read() -> None:
    files = _project(**{"pressed.evt": {"source": "ui"}})
    files[PurePosixPath("broken.sec")] = b"{"

    assert [code for code, *_ in _found(files)] == [
        CoreErrorCode.FILE_INVALID_JSON,
        CoreErrorCode.SCHEMA_UNEXPECTED_FIELD,
        CoreErrorCode.SCHEMA_UNEXPECTED_FIELD,
    ]
