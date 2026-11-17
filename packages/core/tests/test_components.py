"""Components: arguments that fit the parameters of the included sequence, and no cycles."""

from primum_core.errors import CoreErrorCode, Severity
from project_builder import Ids, Project

LED = 4


def _component(project: Project, ids: Ids) -> Project:
    """``Blink(target: element, times: integer)``."""
    return project.add(
        "blink.sec",
        "sequence",
        ids(20),
        name="Blink",
        parameters=[
            {"id": ids(21), "name": "target", "type": "element"},
            {"id": ids(22), "name": "times", "type": "integer"},
        ],
        tracks=[{"element": ids(21), "clips": list[object]()}],
    )


def _show(project: Project, ids: Ids, *arguments: dict[str, object]) -> Project:
    """A sequence that includes Blink once, with ``arguments``."""
    return project.add(
        "show.sec",
        "sequence",
        ids(23),
        name="Show",
        tracks=[],
        blocks=[{"id": ids(24), "sequence": ids(20), "atMs": 0, "arguments": list(arguments)}],
    )


def test_arguments_that_fit_every_parameter_pass(project: Project, ids: Ids) -> None:
    _component(project, ids)
    _show(
        project,
        ids,
        {"parameter": ids(21), "element": ids(LED)},
        {"parameter": ids(22), "value": 3},
    )

    assert project.found() == []


def test_every_parameter_needs_an_argument(project: Project, ids: Ids) -> None:
    _component(project, ids)
    _show(project, ids, {"parameter": ids(21), "element": ids(LED)})

    assert project.found() == [
        (CoreErrorCode.ARGUMENT_MISSING, {"parameter": "times"}, "show.sec", "/blocks/0")
    ]


def test_a_parameter_is_given_once(project: Project, ids: Ids) -> None:
    _component(project, ids)
    _show(
        project,
        ids,
        {"parameter": ids(21), "element": ids(LED)},
        {"parameter": ids(22), "value": 3},
        {"parameter": ids(22), "value": 4},
    )

    assert project.found() == [
        (
            CoreErrorCode.ARGUMENT_DUPLICATE,
            {"parameter": "times"},
            "show.sec",
            "/blocks/0/arguments/2",
        )
    ]


def test_an_element_parameter_takes_an_element_and_the_others_a_value(
    project: Project, ids: Ids
) -> None:
    _component(project, ids)
    _show(
        project,
        ids,
        {"parameter": ids(21), "value": 3},
        {"parameter": ids(22), "element": ids(LED)},
    )

    assert project.found() == [
        (
            CoreErrorCode.SCHEMA_UNEXPECTED_FIELD,
            {"field": "blocks[0].arguments[0].value"},
            "show.sec",
            "/blocks/0/arguments/0/value",
        ),
        (
            CoreErrorCode.ARGUMENT_EXPECTED_ELEMENT,
            {"parameter": "target"},
            "show.sec",
            "/blocks/0/arguments/0",
        ),
        (
            CoreErrorCode.SCHEMA_UNEXPECTED_FIELD,
            {"field": "blocks[0].arguments[1].element"},
            "show.sec",
            "/blocks/0/arguments/1/element",
        ),
        (
            CoreErrorCode.ARGUMENT_EXPECTED_VALUE,
            {"parameter": "times"},
            "show.sec",
            "/blocks/0/arguments/1",
        ),
    ]


def test_a_value_argument_is_of_the_parameters_type(project: Project, ids: Ids) -> None:
    _component(project, ids)
    _show(
        project,
        ids,
        {"parameter": ids(21), "element": ids(LED)},
        {"parameter": ids(22), "value": "three"},
    )

    assert project.found() == [
        (
            CoreErrorCode.VALUE_EXPECTED_INTEGER,
            {"field": "blocks[0].arguments[1].value"},
            "show.sec",
            "/blocks/0/arguments/1/value",
        )
    ]


def test_a_sequence_that_includes_itself_is_an_error(project: Project, ids: Ids) -> None:
    project.add(
        "loop.sec",
        "sequence",
        ids(20),
        name="Loop",
        tracks=[],
        blocks=[{"id": ids(21), "sequence": ids(20), "atMs": 0}],
    )

    assert project.found() == [
        (CoreErrorCode.SEQUENCE_INCLUDES_ITSELF, {"sequence": "Loop"}, "loop.sec", "/blocks/0")
    ]


def test_sequences_that_include_each_other_in_a_loop_are_reported_once(
    project: Project, ids: Ids
) -> None:
    for number, name, included in ((20, "A", 21), (21, "B", 22), (22, "C", 20)):
        project.add(
            f"{name}.sec",
            "sequence",
            ids(number),
            name=name,
            tracks=[],
            blocks=[{"id": ids(number + 10), "sequence": ids(included), "atMs": 0}],
        )

    assert project.found(severity=Severity.ERROR) == [
        (CoreErrorCode.SEQUENCE_CYCLE, {"sequence": "C", "chain": ("A", "B")}, "C.sec", "/blocks/0")
    ]


def test_including_the_same_sequence_twice_is_not_a_cycle(project: Project, ids: Ids) -> None:
    project.add("leaf.sec", "sequence", ids(20), name="Leaf", tracks=[])
    project.add(
        "show.sec",
        "sequence",
        ids(23),
        name="Show",
        tracks=[],
        blocks=[
            {"id": ids(24), "sequence": ids(20), "atMs": 0},
            {"id": ids(25), "sequence": ids(20), "atMs": 1000},
        ],
    )

    assert project.found() == []


def test_a_chain_of_thousands_of_inclusions_is_walked_without_recursion(
    project: Project, ids: Ids
) -> None:
    depth = 3000
    for number in range(depth):
        blocks = [{"id": ids(10_000 + number), "sequence": ids(100 + number + 1), "atMs": 0}]
        project.add(
            f"s{number}.sec",
            "sequence",
            ids(100 + number),
            name=f"S{number}",
            tracks=[],
            blocks=blocks if number < depth - 1 else [],
        )

    assert project.found() == []
