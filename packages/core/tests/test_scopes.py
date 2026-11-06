"""Names of constants and variables: visible by folder, exported and imported, used."""

from primum_core.errors import CoreErrorCode, Severity
from project_builder import Ids, Project


def _variable(ids: Ids, number: int, name: str, **fields: object) -> dict[str, object]:
    return {"id": ids(number), "name": name, "type": "integer", "initial": 0, **fields}


def _automation(project: Project, ids: Ids, path: str, **fields: object) -> Project:
    project.add("start.evt", "event", ids(30), name="Start", source="ui")
    document: dict[str, object] = {
        "name": "Count",
        "when": [ids(30)],
        "do": [{"action": "increment_variable", "variable": "visits"}],
        **fields,
    }
    return project.add(path, "automation", ids(31), **document)


def test_a_file_sees_the_names_of_its_folder_and_of_the_folders_above(
    project: Project, ids: Ids
) -> None:
    project.add(
        "shop.vars", "variables", ids(10), constants=[], variables=[_variable(ids, 11, "visits")]
    )
    _automation(project, ids, "scenes/night/count.auto")

    assert project.found() == []


def test_a_file_never_sees_the_names_of_a_sibling_or_child_folder(
    project: Project, ids: Ids
) -> None:
    project.add(
        "scenes/scenes.vars",
        "variables",
        ids(10),
        constants=[],
        variables=[_variable(ids, 11, "visits")],
    )
    _automation(project, ids, "count.auto")

    assert project.found(severity=Severity.ERROR) == [
        (CoreErrorCode.NAME_UNKNOWN, {"name": "visits"}, "count.auto", "/do/0/variable")
    ]


def test_a_name_defined_again_in_an_inner_folder_is_an_error(project: Project, ids: Ids) -> None:
    project.add(
        "shop.vars", "variables", ids(10), constants=[], variables=[_variable(ids, 11, "visits")]
    )
    project.add(
        "scenes/scenes.vars",
        "variables",
        ids(12),
        constants=[],
        variables=[_variable(ids, 13, "visits")],
    )
    _automation(project, ids, "count.auto")

    assert project.found(severity=Severity.ERROR) == [
        (
            CoreErrorCode.NAME_REDEFINED,
            {"name": "visits", "other": "shop.vars"},
            "scenes/scenes.vars",
            "/variables/0",
        )
    ]


def test_a_name_defined_twice_in_the_same_folder_is_an_error(project: Project, ids: Ids) -> None:
    project.add(
        "a.vars", "variables", ids(10), constants=[], variables=[_variable(ids, 11, "visits")]
    )
    project.add(
        "b.vars",
        "variables",
        ids(12),
        constants=[{"id": ids(13), "name": "visits", "type": "text", "value": "x"}],
        variables=[],
    )
    _automation(project, ids, "count.auto")

    assert project.found(severity=Severity.ERROR) == [
        (
            CoreErrorCode.NAME_REDEFINED,
            {"name": "visits", "other": "a.vars"},
            "b.vars",
            "/constants/0",
        )
    ]


def test_an_exported_name_is_used_after_importing_it(project: Project, ids: Ids) -> None:
    project.add(
        "counters/counters.vars",
        "variables",
        ids(10),
        constants=[],
        variables=[_variable(ids, 11, "visits")],
        exports=["visits"],
    )
    project.add(
        "scenes/scenes.vars",
        "variables",
        ids(12),
        constants=[],
        variables=[],
        imports=[{"from": ids(10), "name": "visits"}],
    )
    _automation(project, ids, "scenes/count.auto")

    assert project.found() == []


def test_importing_a_name_the_file_does_not_export_is_an_error(project: Project, ids: Ids) -> None:
    project.add(
        "counters/counters.vars",
        "variables",
        ids(10),
        constants=[],
        variables=[_variable(ids, 11, "visits"), _variable(ids, 14, "hidden")],
        exports=["visits"],
    )
    project.add(
        "scenes/scenes.vars",
        "variables",
        ids(12),
        constants=[],
        variables=[],
        imports=[{"from": ids(10), "name": "hidden"}, {"from": ids(10), "name": "missing"}],
    )
    _automation(project, ids, "scenes/count.auto")

    errors = project.found(severity=Severity.ERROR)
    assert (
        CoreErrorCode.NAME_NOT_EXPORTED,
        {"name": "hidden"},
        "scenes/scenes.vars",
        "/imports/0/name",
    ) in errors
    assert (
        CoreErrorCode.NAME_UNKNOWN,
        {"name": "missing"},
        "scenes/scenes.vars",
        "/imports/1/name",
    ) in errors


def test_exporting_a_name_the_file_does_not_define_is_an_error(project: Project, ids: Ids) -> None:
    project.add(
        "shop.vars",
        "variables",
        ids(10),
        constants=[],
        variables=[_variable(ids, 11, "visits")],
        exports=["ghost"],
    )
    _automation(project, ids, "count.auto")

    assert project.found(severity=Severity.ERROR) == [
        (CoreErrorCode.NAME_UNKNOWN, {"name": "ghost"}, "shop.vars", "/exports/0")
    ]


def test_a_constant_cannot_be_changed(project: Project, ids: Ids) -> None:
    project.add(
        "shop.vars",
        "variables",
        ids(10),
        constants=[{"id": ids(11), "name": "visits", "type": "integer", "value": 1}],
        variables=[],
    )
    _automation(project, ids, "count.auto")

    assert project.found(severity=Severity.ERROR) == [
        (CoreErrorCode.NAME_NOT_A_VARIABLE, {"name": "visits"}, "count.auto", "/do/0/variable")
    ]


def test_only_a_numeric_variable_is_incremented(project: Project, ids: Ids) -> None:
    project.add(
        "shop.vars",
        "variables",
        ids(10),
        constants=[],
        variables=[_variable(ids, 11, "visits", type="text", initial="")],
    )
    _automation(project, ids, "count.auto")

    assert project.found(severity=Severity.ERROR) == [
        (CoreErrorCode.VARIABLE_NOT_NUMERIC, {"name": "visits"}, "count.auto", "/do/0/variable")
    ]


def test_the_value_set_or_added_is_of_the_variables_type(project: Project, ids: Ids) -> None:
    project.add(
        "shop.vars", "variables", ids(10), constants=[], variables=[_variable(ids, 11, "visits")]
    )
    _automation(
        project,
        ids,
        "count.auto",
        do=[
            {"action": "set_variable", "variable": "visits", "value": "many"},
            {"action": "increment_variable", "variable": "visits", "value": 0.5},
        ],
    )

    assert project.found(severity=Severity.ERROR) == [
        (
            CoreErrorCode.VALUE_EXPECTED_INTEGER,
            {"field": "do[0].value"},
            "count.auto",
            "/do/0/value",
        ),
        (
            CoreErrorCode.VALUE_EXPECTED_INTEGER,
            {"field": "do[1].value"},
            "count.auto",
            "/do/1/value",
        ),
    ]


def test_a_name_nothing_uses_is_a_warning(project: Project, ids: Ids) -> None:
    project.add(
        "shop.vars",
        "variables",
        ids(10),
        constants=[],
        variables=[_variable(ids, 11, "visits"), _variable(ids, 12, "idle")],
    )
    _automation(project, ids, "count.auto")

    assert project.found(severity=Severity.WARNING) == [
        (CoreErrorCode.NAME_UNUSED, {"name": "idle"}, "shop.vars", "/variables/1")
    ]
    assert project.is_valid()


def test_a_word_of_a_condition_an_export_or_a_setting_count_as_uses(
    project: Project, ids: Ids
) -> None:
    project.add(
        "shop.vars",
        "variables",
        ids(10),
        constants=[{"id": ids(13), "name": "limit", "type": "integer", "value": 100}],
        variables=[
            _variable(ids, 11, "visits"),
            _variable(ids, 12, "shared"),
            _variable(ids, 14, "brightness", setting=True),
        ],
        exports=["shared"],
    )
    _automation(project, ids, "count.auto", **{"if": "visits < limit"})

    assert project.found() == []


def test_parameters_are_the_innermost_scope(project: Project, ids: Ids) -> None:
    project.add(
        "shop.vars",
        "variables",
        ids(10),
        constants=[],
        variables=[_variable(ids, 11, "visits", setting=True)],
    )
    project.add(
        "blink.sec",
        "sequence",
        ids(20),
        name="Blink",
        parameters=[
            {"id": ids(21), "name": "visits", "type": "integer"},
            {"id": ids(22), "name": "times", "type": "integer"},
            {"id": ids(23), "name": "times", "type": "number"},
        ],
        tracks=[],
    )

    assert project.found(severity=Severity.ERROR) == [
        (
            CoreErrorCode.NAME_REDEFINED,
            {"name": "visits", "other": "shop.vars"},
            "blink.sec",
            "/parameters/0",
        ),
        (
            CoreErrorCode.NAME_REDEFINED,
            {"name": "times", "other": "blink.sec"},
            "blink.sec",
            "/parameters/2",
        ),
    ]
