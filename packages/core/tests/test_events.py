"""An event that listens to an element, against what its driver says the element tells."""

from primum_core.errors import CoreErrorCode
from project_builder import Ids, Project

BOARD = 3
PULL_UP = {"name": "pull", "value": "up"}


def _hardware(project: Project, ids: Ids) -> Project:
    board = {"id": ids(BOARD), "name": "Pi", "model": "rpi4b"}
    wired = {"board": ids(BOARD)}
    elements = [
        {"id": ids(4), "name": "LED", "type": "digital_output", "pin": 17, **wired},
        {"id": ids(5), "name": "Button", "type": "digital_input", "pin": 27, **wired}
        | {"config": [PULL_UP]},
        {"id": ids(7), "name": "Expander", "type": "i2c_device", "bus": "i2c1", **wired}
        | {"address": 32},
    ]
    return project.add("hardware.hw", "hardware", ids(2), boards=[board], elements=elements)


def _event(project: Project, ids: Ids, element: int, trigger: str = "on") -> Project:
    fields = {"name": "Pressed", "source": "element", "element": ids(element), "trigger": trigger}
    return project.add("pressed.evt", "event", ids(30), **fields)


def test_an_event_listens_to_what_the_driver_of_its_element_tells(
    project: Project, ids: Ids
) -> None:
    for trigger in ("on", "off"):
        _event(_hardware(project, ids), ids, 5, trigger)

        assert project.found() == []


def test_an_element_whose_type_tells_nothing_cannot_start_an_event(
    project: Project, ids: Ids
) -> None:
    _event(_hardware(project, ids), ids, 7)

    assert project.found() == [
        (
            CoreErrorCode.EVENT_TRIGGER_UNAVAILABLE,
            {"element": "Expander", "trigger": "on", "available": ()},
            "pressed.evt",
            "/element",
        )
    ]


def test_an_output_is_reported_once_as_the_wrong_kind_of_element(
    project: Project, ids: Ids
) -> None:
    _event(_hardware(project, ids), ids, 4)

    assert [code for code, *_ in project.found()] == [CoreErrorCode.REF_WRONG_KIND]
