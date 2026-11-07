"""Clips of one element that overlap within a sequence; sequences that may run at once."""

from primum_core.errors import CoreErrorCode, Severity
from project_builder import Ids, Project

LED, BUTTON = 4, 5


def _clip(ids: Ids, number: int, at_ms: int, duration_ms: int) -> dict[str, object]:
    return {"id": ids(number), "atMs": at_ms, "durationMs": duration_ms, "action": "on"}


def _sequence(
    project: Project,
    ids: Ids,
    number: int,
    name: str,
    tracks: list[dict[str, object]],
    **fields: object,
) -> Project:
    return project.add(
        f"{name.lower()}.sec", "sequence", ids(number), name=name, tracks=tracks, **fields
    )


def _started(project: Project, ids: Ids, *sequences: int) -> Project:
    """One automation per sequence, each from its own UI event."""
    for index, number in enumerate(sequences):
        project.add(f"e{index}.evt", "event", ids(60 + index), name=f"Event {index}", source="ui")
        project.add(
            f"a{index}.auto",
            "automation",
            ids(70 + index),
            name=f"Start {index}",
            when=[ids(60 + index)],
            do=[{"action": "start_sequence", "sequence": ids(number)}],
        )
    return project


def test_clips_of_one_element_that_touch_do_not_overlap(project: Project, ids: Ids) -> None:
    _sequence(
        project,
        ids,
        20,
        "Blink",
        [{"element": ids(LED), "clips": [_clip(ids, 21, 0, 500), _clip(ids, 22, 500, 500)]}],
    )

    assert project.found() == []


def test_a_clip_starting_before_the_previous_one_ends_is_an_error(
    project: Project, ids: Ids
) -> None:
    _sequence(
        project,
        ids,
        20,
        "Blink",
        [{"element": ids(LED), "clips": [_clip(ids, 21, 0, 500), _clip(ids, 22, 400, 500)]}],
    )

    assert project.found() == [
        (
            CoreErrorCode.TRACK_CLIPS_OVERLAP,
            {"element": "LED", "atMs": 400},
            "blink.sec",
            "/tracks/0/clips/1",
        )
    ]


def test_clips_on_different_elements_never_overlap(project: Project, ids: Ids) -> None:
    _sequence(
        project,
        ids,
        20,
        "Blink",
        [
            {"element": ids(LED), "clips": [_clip(ids, 21, 0, 500)]},
            {"element": ids(BUTTON), "clips": [_clip(ids, 22, 0, 500)]},
        ],
    )

    assert project.found() == []


def test_a_clip_that_takes_no_time_overlaps_nothing(project: Project, ids: Ids) -> None:
    _sequence(
        project,
        ids,
        20,
        "Blink",
        [{"element": ids(LED), "clips": [_clip(ids, 21, 0, 500), _clip(ids, 22, 100, 0)]}],
    )

    assert project.found() == []


def test_an_included_sequence_counts_at_its_offset(project: Project, ids: Ids) -> None:
    _sequence(project, ids, 20, "Blink", [{"element": ids(LED), "clips": [_clip(ids, 21, 0, 500)]}])
    _sequence(
        project,
        ids,
        23,
        "Show",
        [{"element": ids(LED), "clips": [_clip(ids, 24, 2200, 300)]}],
        blocks=[{"id": ids(25), "sequence": ids(20), "atMs": 2000}],
    )

    assert project.found() == [
        (
            CoreErrorCode.TRACK_CLIPS_OVERLAP,
            {"element": "LED", "atMs": 2200},
            "show.sec",
            "/tracks/0/clips/0",
        )
    ]


def test_an_overlap_coming_through_a_block_is_reported_at_the_block(
    project: Project, ids: Ids
) -> None:
    _sequence(project, ids, 20, "Blink", [{"element": ids(LED), "clips": [_clip(ids, 21, 0, 500)]}])
    _sequence(
        project,
        ids,
        23,
        "Show",
        [{"element": ids(LED), "clips": [_clip(ids, 24, 0, 300)]}],
        blocks=[{"id": ids(25), "sequence": ids(20), "atMs": 100}],
    )

    assert project.found() == [
        (
            CoreErrorCode.TRACK_CLIPS_OVERLAP,
            {"element": "LED", "atMs": 100},
            "show.sec",
            "/blocks/0",
        )
    ]


def test_a_component_plays_the_element_it_is_given(project: Project, ids: Ids) -> None:
    _sequence(
        project,
        ids,
        20,
        "Blink",
        [{"element": ids(26), "clips": [_clip(ids, 21, 0, 500)]}],
        parameters=[{"id": ids(26), "name": "target", "type": "element"}],
    )
    _sequence(
        project,
        ids,
        23,
        "Show",
        [{"element": ids(LED), "clips": [_clip(ids, 24, 0, 300)]}],
        blocks=[
            {
                "id": ids(25),
                "sequence": ids(20),
                "atMs": 0,
                "arguments": [{"parameter": ids(26), "element": ids(LED)}],
            }
        ],
    )

    assert [code for code, *_ in project.found()] == [CoreErrorCode.TRACK_CLIPS_OVERLAP]


def test_started_sequences_sharing_an_element_are_a_warning(project: Project, ids: Ids) -> None:
    _sequence(
        project, ids, 20, "Welcome", [{"element": ids(LED), "clips": [_clip(ids, 21, 0, 500)]}]
    )
    _sequence(project, ids, 23, "Close", [{"element": ids(LED), "clips": [_clip(ids, 24, 0, 500)]}])
    _started(project, ids, 20, 23)

    assert project.found() == [
        (
            CoreErrorCode.SEQUENCE_MAY_OVERLAP,
            {"sequence": "Welcome", "other": "Close", "element": "LED"},
            "welcome.sec",
            "",
        )
    ]
    assert project.is_valid()


def test_sequences_in_one_exclusive_group_or_on_different_priorities_do_not_warn(
    project: Project, ids: Ids
) -> None:
    _sequence(
        project,
        ids,
        20,
        "Welcome",
        [{"element": ids(LED), "clips": [_clip(ids, 21, 0, 500)]}],
        exclusiveGroup="shop",
    )
    _sequence(
        project,
        ids,
        23,
        "Close",
        [{"element": ids(LED), "clips": [_clip(ids, 24, 0, 500)]}],
        exclusiveGroup="shop",
    )
    _sequence(
        project,
        ids,
        27,
        "Night",
        [{"element": ids(LED), "clips": [_clip(ids, 28, 0, 500)]}],
        priority=5,
    )
    _started(project, ids, 20, 23, 27)

    assert project.found(severity=Severity.WARNING) == []


def test_a_sequence_nothing_starts_is_not_compared(project: Project, ids: Ids) -> None:
    _sequence(
        project, ids, 20, "Welcome", [{"element": ids(LED), "clips": [_clip(ids, 21, 0, 500)]}]
    )
    _sequence(project, ids, 23, "Close", [{"element": ids(LED), "clips": [_clip(ids, 24, 0, 500)]}])
    _started(project, ids, 20)

    assert project.found() == []
