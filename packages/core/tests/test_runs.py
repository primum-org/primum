"""Which sequences are running (decision 0023): ``start``, ``stop``, ``still_running``.

The last tests are the cases the plan asked to decide the policy with, checked with
``command_at``: what people write first has to work.
"""

from uuid import UUID

import pytest

from primum_core.commands import Running, Timelines, command_at, timelines_of
from primum_core.runs import start, still_running, stop
from project_builder import Ids, Project

LAMP = 9
ON, OFF, OTHER = 20, 30, 40
DAY = 24 * 60 * 60 * 1000
DUSK, NIGHT = 19 * 60 * 60 * 1000, 23 * 60 * 60 * 1000


def _clip(ids: Ids, number: int, at_ms: int, duration_ms: int, action: str) -> dict[str, object]:
    clip: dict[str, object] = {"id": ids(number), "atMs": at_ms, "durationMs": duration_ms}
    if action == "fade":
        fade = [{"name": "from", "value": 100}, {"name": "to", "value": 0}]
        return {**clip, "action": action, "arguments": fade}
    return {**clip, "action": action}


def _lamp(project: Project, ids: Ids) -> Project:
    lamp = {"id": ids(LAMP), "name": "Lamp", "board": ids(3), "type": "pwm_output", "pin": 18}
    return project.add("lamp.hw", "hardware", ids(8), boards=[], elements=[lamp])


def _sequence(
    project: Project,
    ids: Ids,
    number: int,
    name: str,
    *clips: tuple[int, int, str],
    **fields: object,
) -> Project:
    """A sequence on the lamp: each clip its start, its length and its action."""
    written = [
        _clip(ids, number + index + 1, at_ms, duration_ms, action)
        for index, (at_ms, duration_ms, action) in enumerate(clips)
    ]
    tracks = [{"element": ids(LAMP), "clips": written}]
    return project.add(
        f"{name.lower()}.sec", "sequence", ids(number), name=name, tracks=tracks, **fields
    )


def _run(ids: Ids, number: int, started_ms: int) -> Running:
    return Running(UUID(ids(number)), started_ms)


def _numbers(ids: Ids, running: tuple[Running, ...]) -> list[tuple[int, int]]:
    """Each running sequence as its number and when it started, in order."""
    numbers = {UUID(ids(number)): number for number in (ON, OFF, OTHER)}
    return [(numbers[run.sequence], run.started_ms) for run in running]


def _lamp_does(ids: Ids, at_ms: int, running: tuple[Running, ...], timelines: Timelines) -> str:
    command = command_at(UUID(ids(LAMP)), at_ms, running, timelines)
    return "safe state" if command is None else command.clip.action


@pytest.fixture
def held(project: Project, ids: Ids) -> Project:
    """*On* and *Off*, each an instant command that holds, and *Other* that lasts a second."""
    _lamp(project, ids)
    _sequence(project, ids, ON, "On", (0, 0, "on"), whenDone="hold")
    _sequence(project, ids, OFF, "Off", (0, 0, "off"), whenDone="hold")
    return _sequence(project, ids, OTHER, "Other", (0, 1000, "on"))


def test_starting_a_sequence_puts_it_last(held: Project, ids: Ids) -> None:
    timelines = timelines_of(held.loaded())

    running = start((), _run(ids, ON, 100), timelines)
    running = start(running, _run(ids, OFF, 200), timelines)

    assert _numbers(ids, running) == [(ON, 100), (OFF, 200)]


def test_starting_a_running_sequence_restarts_it(held: Project, ids: Ids) -> None:
    timelines = timelines_of(held.loaded())
    running = (_run(ids, ON, 100), _run(ids, OFF, 200))

    assert _numbers(ids, start(running, _run(ids, ON, 300), timelines)) == [(OFF, 200), (ON, 300)]


def test_a_sequence_that_ignores_being_started_again_goes_on_as_it_was(
    project: Project, ids: Ids
) -> None:
    _lamp(project, ids)
    _sequence(project, ids, ON, "On", (0, 0, "on"), whenDone="hold", whenStartedAgain="ignore")
    _sequence(project, ids, OFF, "Off", (0, 0, "off"), whenDone="hold")
    timelines = timelines_of(project.loaded())
    running = (_run(ids, ON, 100), _run(ids, OFF, 200))

    assert _numbers(ids, start(running, _run(ids, ON, 300), timelines)) == [(ON, 100), (OFF, 200)]


def test_a_sequence_that_ignores_being_started_again_starts_once_it_has_ended(
    project: Project, ids: Ids
) -> None:
    _lamp(project, ids)
    _sequence(project, ids, OTHER, "Other", (0, 1000, "on"), whenStartedAgain="ignore")
    timelines = timelines_of(project.loaded())
    running = (_run(ids, OTHER, 0),)

    assert _numbers(ids, start(running, _run(ids, OTHER, 999), timelines)) == [(OTHER, 0)]
    assert _numbers(ids, start(running, _run(ids, OTHER, 1000), timelines)) == [(OTHER, 1000)]


def test_a_sequence_stops_running_when_its_last_clip_ends_unless_it_holds(
    held: Project, ids: Ids
) -> None:
    timelines = timelines_of(held.loaded())
    running = (_run(ids, ON, 0), _run(ids, OTHER, 500))

    assert _numbers(ids, still_running(running, 1499, timelines)) == [(ON, 0), (OTHER, 500)]
    assert _numbers(ids, still_running(running, 1500, timelines)) == [(ON, 0)]
    assert _numbers(ids, still_running(running, DAY, timelines)) == [(ON, 0)]


def test_starting_a_sequence_stops_the_others_of_its_exclusive_group(
    project: Project, ids: Ids
) -> None:
    _lamp(project, ids)
    _sequence(project, ids, ON, "On", (0, 0, "on"), whenDone="hold", exclusiveGroup="lamp")
    _sequence(project, ids, OFF, "Off", (0, 0, "off"), whenDone="hold", exclusiveGroup="lamp")
    _sequence(project, ids, OTHER, "Other", (0, 0, "on"), whenDone="hold", exclusiveGroup="else")
    timelines = timelines_of(project.loaded())
    running = (_run(ids, ON, 100), _run(ids, OTHER, 200))

    assert _numbers(ids, start(running, _run(ids, OFF, 300), timelines)) == [
        (OTHER, 200),
        (OFF, 300),
    ]


def test_a_sequence_in_no_group_stops_no_other(project: Project, ids: Ids) -> None:
    _lamp(project, ids)
    _sequence(project, ids, ON, "On", (0, 0, "on"), whenDone="hold", exclusiveGroup="lamp")
    _sequence(project, ids, OFF, "Off", (0, 0, "off"), whenDone="hold")
    timelines = timelines_of(project.loaded())

    running = start((_run(ids, ON, 100),), _run(ids, OFF, 200), timelines)

    assert _numbers(ids, running) == [(ON, 100), (OFF, 200)]


def test_stopping_a_sequence_takes_it_out_and_one_not_running_changes_nothing(
    held: Project, ids: Ids
) -> None:
    running = (_run(ids, ON, 100), _run(ids, OFF, 200))

    assert _numbers(ids, stop(running, UUID(ids(ON)))) == [(OFF, 200)]
    assert _numbers(ids, stop(running, UUID(ids(OTHER)))) == [(ON, 100), (OFF, 200)]


def test_a_sequence_that_is_not_of_the_project_is_the_callers_mistake(
    held: Project, ids: Ids
) -> None:
    timelines = timelines_of(held.loaded())

    with pytest.raises(ValueError, match="not among the timelines"):
        start((), _run(ids, 77, 0), timelines)
    with pytest.raises(ValueError, match="not among the timelines"):
        still_running((_run(ids, 77, 0),), 0, timelines)


def test_on_and_off_each_started_by_its_automation_work_day_after_day(
    held: Project, ids: Ids
) -> None:
    timelines = timelines_of(held.loaded())
    running: tuple[Running, ...] = ()
    seen: list[str] = []

    for day in range(3):
        running = start(running, _run(ids, ON, day * DAY + DUSK), timelines)
        seen.append(_lamp_does(ids, day * DAY + DUSK + 1, running, timelines))
        running = start(running, _run(ids, OFF, day * DAY + NIGHT), timelines)
        seen.append(_lamp_does(ids, day * DAY + NIGHT + 1, running, timelines))

    assert seen == ["on", "off"] * 3


def test_an_on_that_ignores_being_started_again_stays_off_from_the_second_day(
    project: Project, ids: Ids
) -> None:
    """Why restarting is the default: ignoring leaves the lamp off for ever."""
    _lamp(project, ids)
    _sequence(project, ids, ON, "On", (0, 0, "on"), whenDone="hold", whenStartedAgain="ignore")
    _sequence(project, ids, OFF, "Off", (0, 0, "off"), whenDone="hold")
    timelines = timelines_of(project.loaded())
    running = start((), _run(ids, ON, DUSK), timelines)
    running = start(running, _run(ids, OFF, NIGHT), timelines)

    running = start(running, _run(ids, ON, DAY + DUSK), timelines)

    assert _lamp_does(ids, DAY + DUSK + 1, running, timelines) == "off"


def test_fading_out_over_an_on_that_holds_gives_the_lamp_back_to_it(
    project: Project, ids: Ids
) -> None:
    _lamp(project, ids)
    _sequence(project, ids, ON, "On", (0, 0, "on"), whenDone="hold")
    _sequence(project, ids, OFF, "Off", (0, 3000, "fade"))
    timelines = timelines_of(project.loaded())
    running = start((_run(ids, ON, DUSK),), _run(ids, OFF, NIGHT), timelines)

    assert _lamp_does(ids, NIGHT + 1000, running, timelines) == "fade"
    after = still_running(running, NIGHT + 3000, timelines)
    assert _lamp_does(ids, NIGHT + 3000, after, timelines) == "on"


def test_fading_out_in_the_exclusive_group_of_on_leaves_the_lamp_off(
    project: Project, ids: Ids
) -> None:
    _lamp(project, ids)
    _sequence(project, ids, ON, "On", (0, 0, "on"), whenDone="hold", exclusiveGroup="lamp")
    _sequence(project, ids, OFF, "Off", (0, 3000, "fade"), exclusiveGroup="lamp")
    timelines = timelines_of(project.loaded())
    running = start((_run(ids, ON, DUSK),), _run(ids, OFF, NIGHT), timelines)

    assert _lamp_does(ids, NIGHT + 1000, running, timelines) == "fade"
    after = still_running(running, NIGHT + 3000, timelines)
    assert _lamp_does(ids, NIGHT + 3000, after, timelines) == "safe state"
    again = start(after, _run(ids, ON, DAY + DUSK), timelines)
    assert _lamp_does(ids, DAY + DUSK + 1, again, timelines) == "on"
