"""Clips of one element that overlap within a sequence; sequences that may run at once."""

from primum_core.errors import CoreErrorCode, Severity
from project_builder import Ids, Project, driver

LED, LAMP = 4, 9


def _clip(ids: Ids, number: int, at_ms: int, duration_ms: int) -> dict[str, object]:
    return {"id": ids(number), "atMs": at_ms, "durationMs": duration_ms, "action": "on"}


def _instant_off(ids: Ids, number: int, at_ms: int) -> dict[str, object]:
    """An instant clip that asks for the safe state: a sequence may end with it."""
    return {**_clip(ids, number, at_ms, 0), "action": "off"}


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


def _with_lamp(project: Project, ids: Ids) -> Project:
    """A second element that takes actions: a PWM lamp on the same Pi."""
    lamp = {"id": ids(LAMP), "name": "Lamp", "board": ids(3), "type": "pwm_output", "pin": 18}
    return project.add("lamp.hw", "hardware", ids(8), boards=[], elements=[lamp])


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
    _with_lamp(project, ids)
    _sequence(
        project,
        ids,
        20,
        "Blink",
        [
            {"element": ids(LED), "clips": [_clip(ids, 21, 0, 500)]},
            {"element": ids(LAMP), "clips": [_clip(ids, 22, 0, 500)]},
        ],
    )

    assert project.found() == []


def _overlaps(project: Project, ids: Ids, *clips: dict[str, object]) -> list[object]:
    """Where the clips of the LED overlap, in one sequence: the ``atMs`` of each report."""
    _sequence(project, ids, 20, "Blink", [{"element": ids(LED), "clips": list(clips)}])
    found = project.found()
    assert all(code is CoreErrorCode.TRACK_CLIPS_OVERLAP for code, *_ in found), found
    return [params["atMs"] for _, params, *_ in found]


def test_an_instant_clip_while_another_clip_runs_overlaps_it(project: Project, ids: Ids) -> None:
    assert _overlaps(project, ids, _clip(ids, 21, 0, 500), _clip(ids, 22, 100, 0)) == [100]


def test_an_instant_clip_where_another_clip_ends_does_not_overlap(
    project: Project, ids: Ids
) -> None:
    assert _overlaps(project, ids, _clip(ids, 21, 0, 500), _clip(ids, 22, 500, 0)) == []


def test_a_clip_that_starts_in_the_instant_of_an_instant_clip_overlaps_it(
    project: Project, ids: Ids
) -> None:
    assert _overlaps(project, ids, _clip(ids, 21, 100, 0), _clip(ids, 22, 100, 500)) == [100]


def test_two_instant_clips_in_the_same_instant_overlap(project: Project, ids: Ids) -> None:
    assert _overlaps(project, ids, _clip(ids, 21, 100, 0), _clip(ids, 22, 100, 0)) == [100]


def test_a_clip_after_an_instant_clip_takes_over_without_overlapping(
    project: Project, ids: Ids
) -> None:
    # The instant clip's effect stays until the next clip of the element starts.
    assert _overlaps(project, ids, _clip(ids, 21, 100, 0), _clip(ids, 22, 101, 500)) == []


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


def test_an_overlap_inside_an_included_sequence_is_reported_there_only(
    project: Project, ids: Ids
) -> None:
    _sequence(
        project,
        ids,
        20,
        "Blink",
        [{"element": ids(LED), "clips": [_clip(ids, 21, 0, 500), _clip(ids, 22, 400, 500)]}],
    )
    _sequence(
        project, ids, 23, "Show", [], blocks=[{"id": ids(25), "sequence": ids(20), "atMs": 0}]
    )
    _sequence(
        project, ids, 26, "Show2", [], blocks=[{"id": ids(27), "sequence": ids(23), "atMs": 0}]
    )

    assert project.found() == [
        (
            CoreErrorCode.TRACK_CLIPS_OVERLAP,
            {"element": "LED", "atMs": 400},
            "blink.sec",
            "/tracks/0/clips/1",
        )
    ]


def test_the_same_component_included_twice_with_crossing_offsets_overlaps(
    project: Project, ids: Ids
) -> None:
    _sequence(project, ids, 20, "Blink", [{"element": ids(LED), "clips": [_clip(ids, 21, 0, 500)]}])
    _sequence(
        project,
        ids,
        23,
        "Show",
        [],
        blocks=[
            {"id": ids(24), "sequence": ids(20), "atMs": 0},
            {"id": ids(25), "sequence": ids(20), "atMs": 300},
        ],
    )

    assert project.found() == [
        (
            CoreErrorCode.TRACK_CLIPS_OVERLAP,
            {"element": "LED", "atMs": 300},
            "show.sec",
            "/blocks/1",
        )
    ]


def test_a_parameter_passed_through_two_levels_of_components_reaches_the_element(
    project: Project, ids: Ids
) -> None:
    _sequence(
        project,
        ids,
        20,
        "Pulse",
        [{"element": ids(30), "clips": [_clip(ids, 21, 0, 500)]}],
        parameters=[{"id": ids(30), "name": "target", "type": "element"}],
    )
    _sequence(
        project,
        ids,
        23,
        "Blink",
        [],
        parameters=[{"id": ids(31), "name": "light", "type": "element"}],
        blocks=[
            {
                "id": ids(24),
                "sequence": ids(20),
                "atMs": 0,
                "arguments": [{"parameter": ids(30), "element": ids(31)}],
            }
        ],
    )
    _sequence(
        project,
        ids,
        26,
        "Show",
        [{"element": ids(LED), "clips": [_clip(ids, 27, 100, 100)]}],
        blocks=[
            {
                "id": ids(28),
                "sequence": ids(23),
                "atMs": 0,
                "arguments": [{"parameter": ids(31), "element": ids(LED)}],
            }
        ],
    )

    assert project.found() == [
        (
            CoreErrorCode.TRACK_CLIPS_OVERLAP,
            {"element": "LED", "atMs": 100},
            "show.sec",
            "/tracks/0/clips/0",
        )
    ]


def test_a_sequence_started_by_two_automations_is_not_compared_with_itself(
    project: Project, ids: Ids
) -> None:
    _sequence(
        project, ids, 20, "Welcome", [{"element": ids(LED), "clips": [_clip(ids, 21, 0, 500)]}]
    )
    _started(project, ids, 20, 20)

    assert project.found() == []


def test_a_clip_on_an_element_the_project_does_not_define_is_only_a_bad_reference(
    project: Project, ids: Ids
) -> None:
    _sequence(
        project,
        ids,
        20,
        "Blink",
        [{"element": ids(99), "clips": [_clip(ids, 21, 0, 500), _clip(ids, 22, 100, 500)]}],
    )

    assert [code for code, *_ in project.found()] == [CoreErrorCode.REF_UNKNOWN]


def test_a_parameter_bound_to_an_element_the_component_also_uses_directly_overlaps(
    project: Project, ids: Ids
) -> None:
    _sequence(
        project,
        ids,
        20,
        "Blink",
        [
            {"element": ids(30), "clips": [_clip(ids, 21, 0, 500)]},
            {"element": ids(LED), "clips": [_clip(ids, 22, 100, 500)]},
        ],
        parameters=[{"id": ids(30), "name": "target", "type": "element"}],
    )
    _sequence(
        project,
        ids,
        23,
        "Show",
        [],
        blocks=[
            {
                "id": ids(24),
                "sequence": ids(20),
                "atMs": 0,
                "arguments": [{"parameter": ids(30), "element": ids(LED)}],
            }
        ],
    )

    assert project.found() == [
        (
            CoreErrorCode.TRACK_CLIPS_OVERLAP,
            {"element": "LED", "atMs": 100},
            "show.sec",
            "/blocks/0",
        )
    ]


def test_started_sequences_sharing_only_an_undefined_element_do_not_warn(
    project: Project, ids: Ids
) -> None:
    _sequence(
        project, ids, 20, "Welcome", [{"element": ids(99), "clips": [_clip(ids, 21, 0, 500)]}]
    )
    _sequence(project, ids, 23, "Close", [{"element": ids(99), "clips": [_clip(ids, 24, 0, 500)]}])
    _started(project, ids, 20, 23)

    assert [code for code, *_ in project.found()] == [CoreErrorCode.REF_UNKNOWN] * 2


def test_a_component_included_twice_is_one_problem_per_block_not_one_per_clip(
    project: Project, ids: Ids
) -> None:
    clips = [_clip(ids, 40 + n, n * 100, 100) for n in range(20)]
    _sequence(project, ids, 20, "Chase", [{"element": ids(LED), "clips": clips}])
    _sequence(
        project,
        ids,
        23,
        "Show",
        [],
        blocks=[
            {"id": ids(24), "sequence": ids(20), "atMs": 0},
            {"id": ids(25), "sequence": ids(20), "atMs": 50},
        ],
    )

    # One per block that takes part, at its first overlap: not one per clip.
    assert project.found() == [
        (
            CoreErrorCode.TRACK_CLIPS_OVERLAP,
            {"element": "LED", "atMs": 50},
            "show.sec",
            "/blocks/1",
        ),
        (
            CoreErrorCode.TRACK_CLIPS_OVERLAP,
            {"element": "LED", "atMs": 100},
            "show.sec",
            "/blocks/0",
        ),
    ]


def test_a_component_included_without_its_element_argument_shares_no_element(
    project: Project, ids: Ids
) -> None:
    _sequence(
        project,
        ids,
        20,
        "Blink",
        [{"element": ids(30), "clips": [_clip(ids, 21, 0, 500)]}],
        parameters=[{"id": ids(30), "name": "target", "type": "element"}],
    )
    for number, name in ((23, "Welcome"), (26, "Close")):
        _sequence(
            project,
            ids,
            number,
            name,
            [],
            blocks=[{"id": ids(number + 1), "sequence": ids(20), "atMs": 0}],
        )
    _started(project, ids, 23, 26)

    assert [code for code, *_ in project.found()] == [CoreErrorCode.ARGUMENT_MISSING] * 2


def test_a_chain_with_a_clip_at_every_level_flattens_and_passes(project: Project, ids: Ids) -> None:
    depth = 300
    for number in range(depth):
        blocks = [{"id": ids(10_000 + number), "sequence": ids(100 + number + 1), "atMs": 1000}]
        project.add(
            f"s{number}.sec",
            "sequence",
            ids(100 + number),
            name=f"S{number}",
            tracks=[{"element": ids(LED), "clips": [_clip(ids, 20_000 + number, 0, 500)]}],
            blocks=blocks if number < depth - 1 else [],
        )

    assert project.found() == []


def test_sequences_that_share_an_element_only_through_instant_clips_may_overlap(
    project: Project, ids: Ids
) -> None:
    for number, name in ((20, "Open"), (30, "Close")):
        clips = [_clip(ids, number + 1, 0, 0), _instant_off(ids, number + 2, 500)]
        _sequence(project, ids, number, name, [{"element": ids(LED), "clips": clips}])
    _started(project, ids, 20, 30)

    assert [code for code, *_ in project.found()] == [CoreErrorCode.SEQUENCE_MAY_OVERLAP]


def _two_started_sequences_on_a_motor(project: Project, ids: Ids, **fields: object) -> Project:
    """Open and Close, both started by automations, both on an element whose driver says one
    sequence owns it while it runs (a motor)."""
    project.drivers["digital_output"] = driver("digital_output", conflictPolicy="exclusive")
    for number, name in ((20, "Open"), (30, "Close")):
        clip = _clip(ids, number + 1, 0, 500)
        _sequence(project, ids, number, name, [{"element": ids(LED), "clips": [clip]}], **fields)
    return _started(project, ids, 20, 30)


def test_sharing_an_element_only_one_sequence_can_use_is_an_error(
    project: Project, ids: Ids
) -> None:
    _two_started_sequences_on_a_motor(project, ids)

    assert project.found(severity=Severity.WARNING) == []
    assert [(code, params["element"]) for code, params, *_ in project.found()] == [
        (CoreErrorCode.SEQUENCE_EXCLUSIVE_ELEMENT_SHARED, "LED")
    ]


def test_an_exclusive_element_shared_within_one_exclusive_group_is_fine(
    project: Project, ids: Ids
) -> None:
    _two_started_sequences_on_a_motor(project, ids, exclusiveGroup="door")

    assert project.found() == []


def test_an_exclusive_element_shared_on_different_priorities_is_fine(
    project: Project, ids: Ids
) -> None:
    """One sequence layers over the other (decision 0006): what the error's hint suggests."""
    project.drivers["digital_output"] = driver("digital_output", conflictPolicy="exclusive")
    for number, name, priority in ((20, "Open", 0), (30, "Close", 5)):
        track: dict[str, object] = {"element": ids(LED), "clips": [_clip(ids, number + 1, 0, 500)]}
        _sequence(project, ids, number, name, [track], priority=priority)
    _started(project, ids, 20, 30)

    assert project.found() == []


def _blink(project: Project, ids: Ids, *clips: dict[str, object]) -> Project:
    """A sequence on the LED with these clips, started by an automation."""
    _sequence(project, ids, 20, "Blink", [{"element": ids(LED), "clips": list(clips)}])
    return _started(project, ids, 20)


def test_an_instant_clip_that_ends_a_started_sequence_is_never_seen(
    project: Project, ids: Ids
) -> None:
    _blink(project, ids, _clip(ids, 21, 0, 0))

    assert project.found(severity=Severity.WARNING) == [
        (
            CoreErrorCode.CLIP_INSTANT_AT_END,
            {"sequence": "Blink", "element": "LED", "action": "on"},
            "blink.sec",
            "/tracks/0/clips/0",
        )
    ]
    assert project.found(severity=Severity.ERROR) == []


def test_an_instant_clip_at_the_end_of_a_sequence_nothing_starts_is_not_reported(
    project: Project, ids: Ids
) -> None:
    _sequence(project, ids, 20, "Blink", [{"element": ids(LED), "clips": [_clip(ids, 21, 0, 0)]}])

    assert project.found() == []


def test_a_sequence_may_end_with_an_instant_clip_that_asks_for_the_safe_state(
    project: Project, ids: Ids
) -> None:
    _blink(project, ids, _clip(ids, 21, 0, 0), _instant_off(ids, 22, 5000))

    assert project.found() == []


def test_an_instant_clip_is_seen_while_another_element_keeps_the_sequence_going(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    tracks: list[dict[str, object]] = [
        {"element": ids(LED), "clips": [_clip(ids, 21, 0, 0)]},
        {"element": ids(LAMP), "clips": [_clip(ids, 22, 0, 500)]},
    ]
    _sequence(project, ids, 20, "Blink", tracks)
    _started(project, ids, 20)

    assert project.found() == []


def test_an_instant_clip_where_the_last_clip_of_another_element_ends_is_never_seen(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    tracks: list[dict[str, object]] = [
        {"element": ids(LED), "clips": [_clip(ids, 21, 500, 0)]},
        {"element": ids(LAMP), "clips": [_clip(ids, 22, 0, 500)]},
    ]
    _sequence(project, ids, 20, "Blink", tracks)
    _started(project, ids, 20)

    assert [(code, pointer) for code, _, _, pointer in project.found()] == [
        (CoreErrorCode.CLIP_INSTANT_AT_END, "/tracks/0/clips/0")
    ]


def test_an_instant_clip_that_ends_a_started_sequence_through_a_block_is_reported_at_the_block(
    project: Project, ids: Ids
) -> None:
    _sequence(project, ids, 30, "Flash", [{"element": ids(LED), "clips": [_clip(ids, 31, 0, 0)]}])
    block = {"id": ids(41), "sequence": ids(30), "atMs": 1000}
    _sequence(project, ids, 20, "Show", [], blocks=[block])
    _started(project, ids, 20)

    assert project.found() == [
        (
            CoreErrorCode.CLIP_INSTANT_AT_END,
            {"sequence": "Show", "element": "LED", "action": "on"},
            "show.sec",
            "/blocks/0",
        )
    ]


def test_an_instant_clip_on_an_element_that_takes_no_clips_is_only_that_problem(
    project: Project, ids: Ids
) -> None:
    project.drivers.pop("digital_output")
    _blink(project, ids, _clip(ids, 21, 0, 0))

    assert [code for code, *_ in project.found()] == [CoreErrorCode.TRACK_ELEMENT_WITHOUT_DRIVER]


def test_two_instant_clips_of_one_element_that_end_a_started_sequence_are_only_an_overlap(
    project: Project, ids: Ids
) -> None:
    _blink(project, ids, _clip(ids, 21, 500, 0), _clip(ids, 22, 500, 0))

    assert [code for code, *_ in project.found()] == [CoreErrorCode.TRACK_CLIPS_OVERLAP]


def test_an_instant_clip_with_an_action_its_element_does_not_have_is_only_that_problem(
    project: Project, ids: Ids
) -> None:
    _blink(project, ids, {**_clip(ids, 21, 0, 0), "action": "onn"})

    assert [code for code, *_ in project.found()] == [CoreErrorCode.ACTION_UNKNOWN]
