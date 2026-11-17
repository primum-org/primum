"""The state each action leaves its element in: what core tells with it."""

from random import Random

import pytest

from primum_core.errors import CoreErrorCode, Severity
from project_builder import Found, Ids, Project

LED, LAMP = 4, 9
SHOW, PART = 20, 40
TARGET = 46  # the element parameter of a component


def _clip(
    ids: Ids, number: int, at_ms: int, duration_ms: int, action: str = "on", **arguments: float
) -> dict[str, object]:
    given = [{"name": name.rstrip("_"), "value": value} for name, value in arguments.items()]
    clip: dict[str, object] = {"id": ids(number), "atMs": at_ms, "durationMs": duration_ms}
    return {**clip, "action": action, "arguments": given}


def _fade_out(ids: Ids, number: int, at_ms: int, duration_ms: int = 2000) -> dict[str, object]:
    return _clip(ids, number, at_ms, duration_ms, "fade", from_=100, to=0)


def _lamp(project: Project, ids: Ids) -> Project:
    lamp = {"id": ids(LAMP), "name": "Lamp", "board": ids(3), "type": "pwm_output", "pin": 18}
    return project.add("lamp.hw", "hardware", ids(8), boards=[], elements=[lamp])


def _show(
    project: Project, ids: Ids, *clips: dict[str, object], element: int = LAMP, **fields: object
) -> Project:
    """A show on the lamp with these clips, and the LED on for a minute so that it goes on."""
    tracks = [
        {"element": ids(element), "clips": list(clips)},
        {"element": ids(LED), "clips": [_clip(ids, 29, 0, 60_000)]},
    ]
    _lamp(project, ids)
    return project.add("show.sec", "sequence", ids(SHOW), name="Show", tracks=tracks, **fields)


def _returns(pointer: str, standing: str = "on") -> Found:
    params: dict[str, object] = {"element": "Lamp", "action": "fade", "standing": standing}
    return (CoreErrorCode.CLIP_RETURNS_TO_INSTANT, params, "show.sec", pointer)


def test_a_fade_to_0_under_a_standing_on_jumps_back_on(project: Project, ids: Ids) -> None:
    _show(project, ids, _clip(ids, 21, 0, 0), _fade_out(ids, 22, 5000))

    assert project.found(severity=Severity.WARNING) == [_returns("/tracks/0/clips/1")]
    assert project.is_valid()


def test_an_instant_off_where_the_fade_ends_keeps_it_off(project: Project, ids: Ids) -> None:
    clips = [_clip(ids, 21, 0, 0), _fade_out(ids, 22, 5000), _clip(ids, 23, 7000, 0, "off")]
    _show(project, ids, *clips)

    assert project.found() == []


def test_an_instant_set_to_0_where_the_fade_ends_keeps_it_off_too(
    project: Project, ids: Ids
) -> None:
    clips = [
        _clip(ids, 21, 0, 0),
        _fade_out(ids, 22, 5000),
        _clip(ids, 23, 7000, 0, "set", level=0),
    ]
    _show(project, ids, *clips)

    assert project.found() == []


def test_an_instant_off_after_the_fade_ended_comes_too_late(project: Project, ids: Ids) -> None:
    clips = [_clip(ids, 21, 0, 0), _fade_out(ids, 22, 5000), _clip(ids, 23, 7001, 0, "off")]
    _show(project, ids, *clips)

    assert project.found() == [_returns("/tracks/0/clips/1")]


def test_a_clip_that_starts_where_the_fade_ends_takes_over(project: Project, ids: Ids) -> None:
    clips = [_clip(ids, 21, 0, 0), _fade_out(ids, 22, 5000), _clip(ids, 23, 7000, 500, "off")]
    _show(project, ids, *clips)

    assert project.found() == []


def test_a_fade_to_0_with_nothing_standing_goes_to_rest(project: Project, ids: Ids) -> None:
    _show(project, ids, _fade_out(ids, 22, 5000))

    assert project.found() == []


def test_a_fade_to_0_under_a_standing_off_stays_off(project: Project, ids: Ids) -> None:
    _show(project, ids, _clip(ids, 21, 0, 0, "set", level=0), _fade_out(ids, 22, 5000))

    assert project.found() == []


def test_a_standing_set_comes_back_as_an_on_does(project: Project, ids: Ids) -> None:
    _show(project, ids, _clip(ids, 21, 0, 0, "set", level=30), _fade_out(ids, 22, 5000))

    assert project.found() == [_returns("/tracks/0/clips/1", "set")]


def test_an_instant_command_replaced_before_the_fade_does_not_come_back(
    project: Project, ids: Ids
) -> None:
    clips = [_clip(ids, 21, 0, 0), _clip(ids, 23, 1000, 0, "off"), _fade_out(ids, 22, 5000)]
    _show(project, ids, *clips)

    assert project.found() == []


def test_an_instant_on_inside_the_fade_cuts_it_which_is_another_matter(
    project: Project, ids: Ids
) -> None:
    """The on commands from 6 s: the fade never reaches 0, so nothing "comes back"."""
    _show(project, ids, _fade_out(ids, 22, 5000), _clip(ids, 23, 6000, 0))

    assert project.found() == []


def test_an_instant_on_where_the_fade_starts_stands_under_it_and_comes_back(
    project: Project, ids: Ids
) -> None:
    _show(project, ids, _clip(ids, 21, 5000, 0), _fade_out(ids, 22, 5000))

    assert project.found() == [_returns("/tracks/0/clips/1")]


def test_a_fade_without_its_from_is_only_that_problem(project: Project, ids: Ids) -> None:
    fade = _clip(ids, 22, 5000, 2000, "fade", to=0)
    _show(project, ids, _clip(ids, 21, 0, 0), fade)

    assert [code for code, *_ in project.found()] == [CoreErrorCode.ACTION_PARAM_MISSING]


def test_a_fade_from_0_to_0_moves_nothing(project: Project, ids: Ids) -> None:
    still = _clip(ids, 22, 5000, 2000, "fade", from_=0, to=0)
    _show(project, ids, _clip(ids, 21, 0, 0), still)

    assert project.found() == []


def test_a_clip_that_holds_0_for_a_while_is_meant_to_give_the_element_back(
    project: Project, ids: Ids
) -> None:
    """Off for two seconds over a standing on is how a light blinks off: no action moves."""
    held = [_clip(ids, 22, 5000, 2000, "off"), _clip(ids, 23, 9000, 2000, "set", level=0)]
    _show(project, ids, _clip(ids, 21, 0, 0), *held)

    assert project.found() == []


def test_a_fade_that_does_not_end_at_rest_is_left_alone(project: Project, ids: Ids) -> None:
    fade = _clip(ids, 22, 5000, 2000, "fade", from_=100, to=30)
    _show(project, ids, _clip(ids, 21, 0, 0), fade)

    assert project.found() == []


def test_a_fade_to_0_that_ends_a_sequence_that_holds_is_kept_at_0(
    project: Project, ids: Ids
) -> None:
    tracks = [{"element": ids(LAMP), "clips": [_clip(ids, 21, 0, 0), _fade_out(ids, 22, 5000)]}]
    _lamp(project, ids)
    project.add("show.sec", "sequence", ids(SHOW), name="Show", tracks=tracks, whenDone="hold")

    assert project.found() == []


def test_a_fade_to_0_that_ends_its_sequence_gives_the_element_to_rest(
    project: Project, ids: Ids
) -> None:
    tracks = [{"element": ids(LAMP), "clips": [_clip(ids, 21, 0, 0), _fade_out(ids, 22, 5000)]}]
    _lamp(project, ids)
    project.add("show.sec", "sequence", ids(SHOW), name="Show", tracks=tracks)

    assert project.found() == []


def _fade_out_component(project: Project, ids: Ids) -> Project:
    """A component that fades its parameter out over two seconds."""
    parameter = {"id": ids(TARGET), "name": "target", "type": "element"}
    tracks = [{"element": ids(TARGET), "clips": [_fade_out(ids, 41, 0)]}]
    return project.add(
        "part.sec", "sequence", ids(PART), name="Part", parameters=[parameter], tracks=tracks
    )


def test_a_component_that_fades_out_is_reported_at_the_block_that_gives_it_a_lit_element(
    project: Project, ids: Ids
) -> None:
    _fade_out_component(project, ids)
    argument = {"parameter": ids(TARGET), "element": ids(LAMP)}
    block = {"id": ids(50), "sequence": ids(PART), "atMs": 5000, "arguments": [argument]}
    _show(project, ids, _clip(ids, 21, 0, 0), blocks=[block])

    assert project.found() == [_returns("/blocks/0")]


def test_a_standing_on_of_an_included_sequence_comes_back_while_its_block_lasts(
    project: Project, ids: Ids
) -> None:
    """Part turns the lamp on in an instant and lasts ten seconds, on the LED."""
    part = [
        {"element": ids(LAMP), "clips": [_clip(ids, 41, 0, 0)]},
        {"element": ids(LED), "clips": [_clip(ids, 42, 0, 10_000)]},
    ]
    project.add("part.sec", "sequence", ids(PART), name="Part", tracks=part)
    block: dict[str, object] = {"id": ids(50), "sequence": ids(PART), "atMs": 0}
    block["arguments"] = []
    fades = [_fade_out(ids, 22, 5000), _fade_out(ids, 23, 9000), _clip(ids, 24, 20_000, 500)]
    _lamp(project, ids)
    tracks = [{"element": ids(LAMP), "clips": fades}]
    project.add("show.sec", "sequence", ids(SHOW), name="Show", tracks=tracks, blocks=[block])

    # The second fade ends after the block: its instant on is over by then.
    assert project.found() == [_returns("/tracks/0/clips/0")]


def test_an_instant_set_to_0_may_end_a_sequence_as_an_off_may(project: Project, ids: Ids) -> None:
    tracks = [
        {
            "element": ids(LAMP),
            "clips": [_clip(ids, 21, 0, 0), _clip(ids, 22, 5000, 0, "set", level=0)],
        }
    ]
    _lamp(project, ids)
    project.add("show.sec", "sequence", ids(SHOW), name="Show", tracks=tracks)

    assert project.found() == []


def test_an_instant_set_above_0_that_ends_a_sequence_is_never_seen(
    project: Project, ids: Ids
) -> None:
    tracks = [
        {
            "element": ids(LAMP),
            "clips": [_clip(ids, 21, 0, 0), _clip(ids, 22, 5000, 0, "set", level=1)],
        }
    ]
    _lamp(project, ids)
    project.add("show.sec", "sequence", ids(SHOW), name="Show", tracks=tracks)

    assert [code for code, *_ in project.found()] == [CoreErrorCode.CLIP_INSTANT_AT_END]


GRID_MS = 500
LENGTH_MS = 2 * GRID_MS


def _random_clips(random: Random, ids: Ids) -> list[dict[str, object]]:
    """Clips of the lamp on a grid: at each point maybe an instant command, and maybe a clip
    of two cells where the last one has ended."""
    clips: list[dict[str, object]] = []
    free_from = 0
    for cell in range(12):
        at_ms = cell * GRID_MS
        number = 100 + 2 * cell
        if random.random() < 0.4:
            level = random.choice([0, 0, 30, 100])
            clips.append(_clip(ids, number, at_ms, 0, "set", level=level))
        if at_ms >= free_from and random.random() < 0.5:
            free_from = at_ms + LENGTH_MS
            if random.random() < 0.7:
                to = random.choice([0, 0, 30])
                clips.append(_clip(ids, number + 1, at_ms, LENGTH_MS, "fade", from_=100, to=to))
            else:
                clips.append(_clip(ids, number + 1, at_ms, LENGTH_MS, "off"))
    return clips


def _expected_to_return(clips: list[dict[str, object]]) -> list[str]:
    """Where the warning belongs, told without asking who commands: a fade to 0, nothing
    starting where it ends, and the last instant command before that, which is not inside
    the fade, asking for more than 0."""

    def number(clip: dict[str, object], field: str) -> int:
        value = clip[field]
        assert isinstance(value, int)
        return value

    def level(clip: dict[str, object], name: str) -> object:
        arguments = clip["arguments"]
        assert isinstance(arguments, list)
        return next(a["value"] for a in arguments if a["name"] == name)  # pyright: ignore

    expected: list[str] = []
    for index, clip in enumerate(clips):
        if clip["action"] != "fade" or level(clip, "to") != 0:
            continue
        end = number(clip, "atMs") + LENGTH_MS
        if any(number(other, "atMs") == end for other in clips):
            continue
        before = [o for o in clips if o["durationMs"] == 0 and number(o, "atMs") < end]
        last = max(before, key=lambda o: number(o, "atMs")) if before else None
        if last is None or number(last, "atMs") > number(clip, "atMs"):
            continue
        if level(last, "level") != 0:
            expected.append(f"/tracks/0/clips/{index}")
    return expected


@pytest.mark.parametrize("seed", range(300))
def test_the_warning_agrees_with_a_rule_written_apart(
    project: Project, ids: Ids, seed: int
) -> None:
    clips = _random_clips(Random(seed), ids)  # noqa: S311 (a fixed seed)
    _show(project, ids, *clips)

    found = [
        pointer
        for code, _, _, pointer in project.found()
        if code is CoreErrorCode.CLIP_RETURNS_TO_INSTANT
    ]
    assert project.is_valid()
    assert sorted(found) == sorted(_expected_to_return(clips))
