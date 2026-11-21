"""Who commands an element at an instant (decision 0017): ``command_at``."""

import json
from pathlib import PurePosixPath
from random import Random
from uuid import UUID

import pytest

from primum_core.commands import Command, Running, command_at, timelines_of
from primum_core.compiler import compile_package
from primum_core.errors import CoreErrorCode
from primum_core.generated.model import Package
from primum_core.package import read_package
from project_builder import Ids, Project

LED, LAMP = 4, 9
SHOW, OTHER, PART = 20, 30, 40
TARGET = 46  # the element parameter of a component
LONG = 60_000


def _clip(
    ids: Ids, number: int, at_ms: int, duration_ms: int, action: str = "on", **arguments: float
) -> dict[str, object]:
    given = [{"name": name.rstrip("_"), "value": value} for name, value in arguments.items()]
    clip: dict[str, object] = {"id": ids(number), "atMs": at_ms, "durationMs": duration_ms}
    return {**clip, "action": action, "arguments": given}


def _sequence(
    project: Project,
    ids: Ids,
    number: int,
    name: str,
    tracks: dict[int, list[dict[str, object]]],
    **fields: object,
) -> Project:
    """A sequence with the clips of each element (or parameter), by its number."""
    written = [{"element": ids(element), "clips": clips} for element, clips in tracks.items()]
    return project.add(
        f"{name.lower()}.sec", "sequence", ids(number), name=name, tracks=written, **fields
    )


def _with_lamp(project: Project, ids: Ids) -> Project:
    """A PWM lamp next to the LED: something that takes ``set`` and ``fade``."""
    lamp = {"id": ids(LAMP), "name": "Lamp", "board": ids(3), "type": "pwm_output", "pin": 18}
    return project.add("lamp.hw", "hardware", ids(8), boards=[], elements=[lamp])


def _asked(
    project: Project, ids: Ids, element: int, at_ms: int, *running: tuple[int, int]
) -> Command | None:
    """What ``element`` is asked at ``at_ms`` with these sequences running: each a number and
    when it started."""
    runs = [Running(UUID(ids(number)), started) for number, started in running]
    return command_at(UUID(ids(element)), at_ms, runs, timelines_of(project.loaded()))


def _action(
    project: Project, ids: Ids, element: int, at_ms: int, *running: tuple[int, int]
) -> tuple[str, bool] | None:
    """The action asked and whether it is settled, or ``None``: the safe state. With no
    sequences given, the show started at 0."""
    command = _asked(project, ids, element, at_ms, *(running or ((SHOW, 0),)))
    return None if command is None else (command.clip.action, command.settled)


def _keeping_the_show_going(ids: Ids) -> list[dict[str, object]]:
    """A long clip for another element, so that the show does not end with the one tested."""
    return [_clip(ids, 29, 0, LONG)]


def test_with_nothing_running_an_element_is_in_its_safe_state(project: Project, ids: Ids) -> None:
    _sequence(project, ids, SHOW, "Show", {LED: [_clip(ids, 21, 0, 500)]})

    assert command_at(UUID(ids(LED)), 100, [], timelines_of(project.loaded())) is None


def test_a_clip_commands_its_element_while_it_lasts(project: Project, ids: Ids) -> None:
    _sequence(project, ids, SHOW, "Show", {LED: [_clip(ids, 21, 1000, 2000)]})

    assert _action(project, ids, LED, 999) is None
    assert _action(project, ids, LED, 1000) == ("on", False)
    assert _action(project, ids, LED, 2999) == ("on", False)
    assert _action(project, ids, LED, 3000) is None


def test_the_time_of_a_sequence_counts_from_when_it_started(project: Project, ids: Ids) -> None:
    _sequence(project, ids, SHOW, "Show", {LED: [_clip(ids, 21, 1000, 2000)]})

    assert _action(project, ids, LED, 10_500, (SHOW, 10_000)) is None
    command = _asked(project, ids, LED, 11_500, (SHOW, 10_000))
    assert command is not None
    assert (command.sequence, command.since_ms) == (UUID(ids(SHOW)), 11_000)
    assert _action(project, ids, LED, 500, (SHOW, 10_000)) is None


def test_an_instant_command_stands_until_its_sequence_ends(project: Project, ids: Ids) -> None:
    _with_lamp(project, ids)
    tracks = {LED: [_clip(ids, 21, 0, 0)], LAMP: [_clip(ids, 22, 0, 5000)]}
    _sequence(project, ids, SHOW, "Show", tracks)

    assert _action(project, ids, LED, 0) == ("on", True)
    assert _action(project, ids, LED, 4999) == ("on", True)
    assert _action(project, ids, LED, 5000) is None


def test_a_clip_plays_over_a_standing_command_and_gives_the_element_back(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    lamp = [_clip(ids, 21, 0, 0), _clip(ids, 22, 5000, 1000, "set", level=30)]
    _sequence(project, ids, SHOW, "Show", {LAMP: lamp, LED: _keeping_the_show_going(ids)})

    assert _action(project, ids, LAMP, 4000) == ("on", True)
    assert _action(project, ids, LAMP, 5500) == ("set", False)
    assert _action(project, ids, LAMP, 6000) == ("on", True)


def test_an_instant_command_inside_a_clip_cuts_it(project: Project, ids: Ids) -> None:
    _with_lamp(project, ids)
    led = [_clip(ids, 21, 5000, 1000), _clip(ids, 22, 5500, 0, "off")]
    _sequence(project, ids, SHOW, "Show", {LED: led, LAMP: _keeping_the_show_going(ids)})

    assert _action(project, ids, LED, 5499) == ("on", False)
    assert _action(project, ids, LED, 5500) == ("off", True)
    assert _action(project, ids, LED, 5900) == ("off", True)
    assert _action(project, ids, LED, 6000) == ("off", True)


def test_a_clip_and_an_instant_command_that_start_together_the_clip_comes_first(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    lamp = [_clip(ids, 21, 0, 0), _clip(ids, 22, 0, 1000, "set", level=30)]
    _sequence(project, ids, SHOW, "Show", {LAMP: lamp, LED: _keeping_the_show_going(ids)})

    assert _action(project, ids, LAMP, 0) == ("set", False)
    assert _action(project, ids, LAMP, 1000) == ("on", True)


def test_the_next_instant_command_of_an_element_replaces_the_one_before(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    led = [_clip(ids, 21, 0, 0), _clip(ids, 22, 2000, 0, "off")]
    _sequence(project, ids, SHOW, "Show", {LED: led, LAMP: _keeping_the_show_going(ids)})

    assert _action(project, ids, LED, 1999) == ("on", True)
    assert _action(project, ids, LED, 2000) == ("off", True)
    assert _action(project, ids, LED, LONG - 1) == ("off", True)


def test_a_fade_out_and_an_instant_off_where_it_ends_leave_the_element_off(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    lamp = [
        _clip(ids, 21, 0, 0),
        _clip(ids, 22, 4000, 1000, "fade", from_=100, to=0),
        _clip(ids, 23, 5000, 0, "off"),
    ]
    _sequence(project, ids, SHOW, "Show", {LAMP: lamp, LED: _keeping_the_show_going(ids)})

    assert _action(project, ids, LAMP, 4500) == ("fade", False)
    assert _action(project, ids, LAMP, 5000) == ("off", True)
    assert _action(project, ids, LAMP, 9000) == ("off", True)


def test_a_fade_out_without_an_instant_off_gives_the_element_back_to_the_standing_on(
    project: Project, ids: Ids
) -> None:
    """The trap decision 0017 names: ``core`` cannot warn about it yet (plan, 3.3)."""
    _with_lamp(project, ids)
    lamp = [_clip(ids, 21, 0, 0), _clip(ids, 22, 4000, 1000, "fade", from_=100, to=0)]
    _sequence(project, ids, SHOW, "Show", {LAMP: lamp, LED: _keeping_the_show_going(ids)})

    assert _action(project, ids, LAMP, 9000) == ("on", True)


def _flash_included_at_two_seconds(project: Project, ids: Ids, **show: object) -> Project:
    """A component that turns its element on for half a second, placed at 2 s of a show that
    lasts a minute and gives it the LED."""
    _with_lamp(project, ids)
    flash = [_clip(ids, 41, 0, 0), _clip(ids, 42, 500, 0, "off")]
    parameter = {"id": ids(TARGET), "name": "target", "type": "element"}
    _sequence(project, ids, PART, "Flash", {TARGET: flash}, parameters=[parameter])
    argument = {"parameter": ids(TARGET), "element": ids(LED)}
    block = {"id": ids(25), "sequence": ids(PART), "atMs": 2000, "arguments": [argument]}
    tracks = {LAMP: _keeping_the_show_going(ids)}
    return _sequence(project, ids, SHOW, "Show", tracks, blocks=[block], **show)


def test_an_instant_command_of_a_component_ends_with_its_block(project: Project, ids: Ids) -> None:
    _flash_included_at_two_seconds(project, ids)

    assert _action(project, ids, LED, 1999) is None
    assert _action(project, ids, LED, 2000) == ("on", True)
    assert _action(project, ids, LED, 2499) == ("on", True)
    assert _action(project, ids, LED, 2500) is None


def test_a_component_gives_the_element_back_to_the_standing_command_of_what_includes_it(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    dim = [_clip(ids, 41, 0, 0, "set", level=30), _clip(ids, 42, 300, 0, "off")]
    parameter = {"id": ids(TARGET), "name": "target", "type": "element"}
    _sequence(project, ids, PART, "Dim", {TARGET: dim}, parameters=[parameter])
    argument = {"parameter": ids(TARGET), "element": ids(LAMP)}
    block = {"id": ids(25), "sequence": ids(PART), "atMs": 2000, "arguments": [argument]}
    tracks = {LAMP: [_clip(ids, 21, 0, 0)], LED: _keeping_the_show_going(ids)}
    _sequence(project, ids, SHOW, "Show", tracks, blocks=[block])

    assert _action(project, ids, LAMP, 1000) == ("on", True)
    assert _action(project, ids, LAMP, 2100) == ("set", True)
    assert _action(project, ids, LAMP, 2300) == ("on", True)


def _two_sequences_on_the_lamp(project: Project, ids: Ids, **show: object) -> Project:
    """The show sets the lamp to 30 for a minute; the other sets it to 80 for two seconds."""
    _with_lamp(project, ids)
    show_clips = {LAMP: [_clip(ids, 21, 0, LONG, "set", level=30)]}
    _sequence(project, ids, SHOW, "Show", show_clips, **show)
    other = {LAMP: [_clip(ids, 31, 0, 2000, "set", level=80)]}
    return _sequence(project, ids, OTHER, "Other", other)


def test_of_two_sequences_of_one_priority_the_command_that_started_last_wins(
    project: Project, ids: Ids
) -> None:
    _two_sequences_on_the_lamp(project, ids)
    running = ((SHOW, 0), (OTHER, 3000))

    before = _asked(project, ids, LAMP, 2000, *running)
    during = _asked(project, ids, LAMP, 3500, *running)
    after = _asked(project, ids, LAMP, 5000, *running)

    assert before is not None and before.sequence == UUID(ids(SHOW))
    assert during is not None and during.sequence == UUID(ids(OTHER))
    assert after is not None and after.sequence == UUID(ids(SHOW))


def test_a_higher_priority_commands_whatever_started_last(project: Project, ids: Ids) -> None:
    _two_sequences_on_the_lamp(project, ids, priority=5)

    command = _asked(project, ids, LAMP, 3500, (SHOW, 0), (OTHER, 3000))

    assert command is not None and command.sequence == UUID(ids(SHOW))


def test_when_a_higher_priority_ends_the_element_goes_to_the_layer_below(
    project: Project, ids: Ids
) -> None:
    _two_sequences_on_the_lamp(project, ids)
    _sequence(project, ids, PART, "Alarm", {LAMP: [_clip(ids, 41, 0, 1000)]}, priority=9)
    running = ((SHOW, 0), (PART, 3000))

    assert _action(project, ids, LAMP, 3500, *running) == ("on", False)
    assert _action(project, ids, LAMP, 4000, *running) == ("set", False)


def test_of_two_commands_that_started_in_one_instant_the_sequence_given_last_wins(
    project: Project, ids: Ids
) -> None:
    _two_sequences_on_the_lamp(project, ids)

    first = _asked(project, ids, LAMP, 500, (SHOW, 0), (OTHER, 0))
    second = _asked(project, ids, LAMP, 500, (OTHER, 0), (SHOW, 0))

    assert first is not None and first.sequence == UUID(ids(OTHER))
    assert second is not None and second.sequence == UUID(ids(SHOW))


def test_a_sequence_that_holds_keeps_its_standing_command_until_it_is_stopped(
    project: Project, ids: Ids
) -> None:
    _sequence(project, ids, SHOW, "Lights", {LED: [_clip(ids, 21, 0, 0)]}, whenDone="hold")

    assert _action(project, ids, LED, 0) == ("on", True)
    assert _action(project, ids, LED, 3_600_000) == ("on", True)
    assert command_at(UUID(ids(LED)), 3_600_000, [], timelines_of(project.loaded())) is None


def test_the_same_sequence_without_holding_is_over_at_once(project: Project, ids: Ids) -> None:
    _sequence(project, ids, SHOW, "Lights", {LED: [_clip(ids, 21, 0, 0)]})

    assert _action(project, ids, LED, 0) is None


def test_a_sequence_that_holds_keeps_the_clip_it_ends_with_as_it_ended(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    fade_in = [_clip(ids, 21, 0, 2000, "fade", from_=0, to=100)]
    _sequence(project, ids, SHOW, "Lights", {LAMP: fade_in}, whenDone="hold")

    assert _action(project, ids, LAMP, 1000) == ("fade", False)
    assert _action(project, ids, LAMP, 2000) == ("fade", True)
    assert _action(project, ids, LAMP, 3_600_000) == ("fade", True)


def test_a_sequence_that_holds_does_not_keep_a_clip_that_ended_before_its_end(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    tracks = {LED: [_clip(ids, 21, 0, 1000)], LAMP: [_clip(ids, 22, 0, 2000)]}
    _sequence(project, ids, SHOW, "Lights", tracks, whenDone="hold")

    assert _action(project, ids, LED, 1500) is None
    assert _action(project, ids, LED, 5000) is None
    assert _action(project, ids, LAMP, 5000) == ("on", True)


def test_a_sequence_that_holds_keeps_what_a_component_left_in_its_last_instant(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    _sequence(project, ids, PART, "Glow", {LAMP: [_clip(ids, 41, 0, 1000)]})
    block = {"id": ids(25), "sequence": ids(PART), "atMs": 500}
    _sequence(project, ids, SHOW, "Lights", {}, blocks=[block], whenDone="hold")

    assert _action(project, ids, LAMP, 9000) == ("on", True)


def test_holding_is_ignored_when_the_sequence_is_included_in_another(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    _sequence(project, ids, PART, "Glow", {LED: [_clip(ids, 41, 0, 500)]}, whenDone="hold")
    block = {"id": ids(25), "sequence": ids(PART), "atMs": 0}
    _sequence(project, ids, SHOW, "Show", {LAMP: _keeping_the_show_going(ids)}, blocks=[block])

    assert _action(project, ids, LED, 600) is None
    assert _action(project, ids, LED, 600, (PART, 0)) == ("on", True)


def test_a_sequence_that_has_not_started_yet_commands_nothing(project: Project, ids: Ids) -> None:
    _sequence(project, ids, SHOW, "Show", {LED: [_clip(ids, 21, 0, 500)]})

    assert _action(project, ids, LED, 100, (SHOW, 5000)) is None


def test_an_element_no_running_sequence_touches_is_in_its_safe_state(
    project: Project, ids: Ids
) -> None:
    _with_lamp(project, ids)
    _sequence(project, ids, SHOW, "Show", {LED: [_clip(ids, 21, 0, 500)]})

    assert _action(project, ids, LAMP, 100) is None


def test_a_block_that_includes_an_empty_sequence_does_not_make_its_sequence_longer(
    project: Project, ids: Ids
) -> None:
    """A sequence ends with its last clip: a block with no clips adds none."""
    project.add("empty.sec", "sequence", ids(PART), name="Empty", tracks=[])
    block = {"id": ids(25), "sequence": ids(PART), "atMs": 5000}
    tracks = {LED: [_clip(ids, 21, 0, 1000)]}
    _sequence(project, ids, SHOW, "Show", tracks, blocks=[block], whenDone="hold")

    # The show ended at 1 s, with its clip, which it therefore holds.
    assert _action(project, ids, LED, 3000) == ("on", True)


def test_a_running_sequence_that_is_not_of_the_project_is_the_callers_mistake(
    project: Project, ids: Ids
) -> None:
    _sequence(project, ids, SHOW, "Show", {LED: [_clip(ids, 21, 0, 500)]})

    with pytest.raises(ValueError, match=ids(OTHER)):
        _asked(project, ids, LED, 100, (OTHER, 0))


def test_the_spans_of_a_sequence_that_holds_show_what_replaced_what(
    project: Project, ids: Ids
) -> None:
    """An instant command the next one replaced is not held; the last one is."""
    _with_lamp(project, ids)
    led = [_clip(ids, 21, 0, 0), _clip(ids, 22, 5000, 0, "off")]
    tracks = {LED: led, LAMP: [_clip(ids, 23, 0, 5000)]}
    _sequence(project, ids, SHOW, "Lights", tracks, whenDone="hold")

    spans = timelines_of(project.loaded())[UUID(ids(SHOW))].spans[UUID(ids(LED))]

    assert [(span.clip.action, span.start, span.until) for span in spans] == [
        ("on", 0, 5000),
        ("off", 5000, None),
    ]


def _random_project(project: Project, ids: Ids, random: Random) -> dict[str, list[str]]:
    """Four sequences on the LED, each with a few clips and blocks of the ones before it, any
    of them holding. Returns the clip ids of each file, in the order they are written."""
    written: dict[str, list[str]] = {}
    for number in range(4):
        clips: list[dict[str, object]] = []
        at_ms = 0
        for index in range(random.randint(0, 3)):
            at_ms += random.choice([0, 500, 1000])
            length = random.choice([0, 0, 500])
            action = random.choice(["on", "off"])
            clips.append(_clip(ids, 100 + number * 10 + index, at_ms, length, action))
            at_ms += max(length, 1)
        blocks = [
            {"id": ids(200 + number * 10 + index), "sequence": ids(300 + included), "atMs": at}
            for index, (included, at) in enumerate(
                (random.randrange(number), random.choice([0, 500, 2000, 3000]))
                for _ in range(random.randint(0, 2) if number else 0)
            )
        ]
        fields: dict[str, object] = {"whenDone": random.choice(["end", "hold"]), "blocks": blocks}
        name = f"S{number}"
        _sequence(project, ids, 300 + number, name, {LED: clips} if clips else {}, **fields)
        written[f"{name.lower()}.sec"] = [str(clip["id"]) for clip in clips]
    return written


@pytest.mark.parametrize("seed", range(300))
def test_a_clip_reported_as_never_seen_never_commands_however_its_sequence_runs(
    project: Project, ids: Ids, seed: int
) -> None:
    """``clip.instant_at_end`` against the oracle, on random projects: no false warning."""
    # A seeded generator: the same projects on every run. Nothing here is a secret.
    written = _random_project(project, ids, Random(seed))  # noqa: S311 (a fixed seed)
    if not project.is_valid():
        return  # two clips overlap: nothing to compare
    timelines = timelines_of(project.loaded())
    reported = {
        written[path][int(pointer.rsplit("/", 1)[1])]
        for code, _, path, pointer in project.found()
        if code is CoreErrorCode.CLIP_INSTANT_AT_END
    }
    instants = range(0, 12_000, 250)

    seen = {
        str(command.clip.id)
        for sequence in timelines
        for at_ms in instants
        if (command := command_at(UUID(ids(LED)), at_ms, [Running(sequence, 0)], timelines))
    }

    assert reported.isdisjoint(seen)


def _asked_of_the_package(
    package: Package, element: UUID, at_ms: int, running: list[Running]
) -> tuple[UUID, bool] | None:
    """What an engine would read from a deployment package: of the commands in force, the
    highest priority, then the one that started last, a clip with a length before an instant
    command, then the sequence started last. Its clip, and whether its action is over."""
    sequences = {sequence.id: sequence for sequence in package.sequences}
    winner: tuple[tuple[int, int, bool, int], tuple[UUID, bool]] | None = None
    for order, run in enumerate(running):
        sequence = sequences[run.sequence]
        local = at_ms - run.started_ms
        for command in sequence.commands:
            ended = command.until_ms is not None and local >= command.until_ms
            if command.element != element or local < command.at_ms or ended:
                continue
            since = run.started_ms + command.at_ms
            rank = (sequence.priority, since, command.duration_ms > 0, order)
            if winner is None or rank > winner[0]:
                settled = local >= command.at_ms + command.duration_ms
                winner = (rank, (command.clip, settled))
    return winner[1] if winner else None


@pytest.mark.parametrize("seed", range(300))
def test_a_deployment_package_says_what_command_at_says(
    project: Project, ids: Ids, seed: int
) -> None:
    """The commands of a compiled package against the oracle, on random projects, with two
    sequences running, started at different times: an engine needs nothing but the package."""
    random = Random(seed)  # noqa: S311 (a fixed seed: the same projects on every run)
    _random_project(project, ids, random)
    for number in range(4):  # priorities too, which the projects above leave at 0
        if random.random() < 0.3:
            path = PurePosixPath(f"s{number}.sec")
            document = json.loads(project.files[path])
            project.files[path] = json.dumps({**document, "priority": 5}).encode()
    if not project.is_valid():
        return
    workspace = project.loaded()
    timelines = timelines_of(workspace)
    compiled = compile_package(workspace)
    assert compiled.value is not None
    package = read_package(PurePosixPath("p.json"), json.dumps(compiled.value).encode()).value
    assert package is not None
    first, second = random.sample(sorted(timelines), 2)
    running = [Running(first, 0), Running(second, random.choice([0, 250, 1000, 4000]))]
    led = UUID(ids(LED))

    for at_ms in range(0, 14_000, 250):
        expected = command_at(led, at_ms, running, timelines)
        asked = _asked_of_the_package(package, led, at_ms, running)
        assert asked == (None if expected is None else (expected.clip.id, expected.settled)), at_ms
