"""The engine against the oracle of ``core``: on random projects, with sequences started and
stopped at random, it runs the same sequences and asks each element the same thing as
``primum_core.runs`` and ``command_at`` say, and nothing changes between two of its changes."""

import json
from pathlib import PurePosixPath
from random import Random
from uuid import UUID

import pytest

from primum_core.commands import Running, command_at, timelines_of
from primum_core.compiler import compile_package
from primum_core.package import read_package
from primum_core.runs import start, still_running, stop
from primum_core.workspace import Workspace, load_workspace
from primum_runtime.board import load_profile
from primum_runtime.drivers import load_manifests
from primum_runtime.engine import Engine
from primum_runtime.errors import ErrorCode, PrimumError

MANIFESTS = load_manifests()
PROFILES = {"rpi4b": load_profile("rpi4b")}
LED = UUID(int=4)
SEQUENCES = [UUID(int=300 + number) for number in range(4)]

type Files = dict[PurePosixPath, bytes]


def _id(number: int) -> str:
    return str(UUID(int=number))


def _file(kind: str, number: int, **fields: object) -> bytes:
    document = {"id": _id(number), "kind": kind, "schemaVersion": 1, **fields}
    return json.dumps(document).encode()


def _project(random: Random) -> Files:
    """A Pi with an LED and four sequences on it: a few clips each, blocks of the ones
    before, and at random a priority, an exclusive group, holding, ignoring a restart."""
    led = {"id": _id(4), "name": "LED", "board": _id(3), "type": "digital_output", "pin": 17}
    board = {"id": _id(3), "name": "Pi", "model": "rpi4b"}
    files: Files = {
        PurePosixPath("project.json"): _file("project", 1, name="Random"),
        PurePosixPath("hardware.hw"): _file("hardware", 2, boards=[board], elements=[led]),
    }
    for number in range(4):
        clips: list[dict[str, object]] = []
        at_ms = 0
        for index in range(random.randint(0, 3)):
            at_ms += random.choice([0, 500, 1000])
            length = random.choice([0, 0, 500])
            clip = {"id": _id(100 + number * 10 + index), "atMs": at_ms, "durationMs": length}
            clips.append({**clip, "action": random.choice(["on", "off"])})
            at_ms += max(length, 1)
        blocks = [
            {
                "id": _id(200 + number * 10 + index),
                "sequence": _id(300 + random.randrange(number)),
                "atMs": random.choice([0, 500, 2000, 3000]),
            }
            for index in range(random.randint(0, 2) if number else 0)
        ]
        fields: dict[str, object] = {
            "name": f"S{number}",
            "tracks": [{"element": _id(4), "clips": clips}] if clips else [],
            "blocks": blocks,
            "whenDone": random.choice(["end", "hold"]),
            "whenStartedAgain": random.choice(["restart", "restart", "ignore"]),
            "priority": random.choice([0, 0, 5]),
        }
        if random.random() < 0.4:
            fields["exclusiveGroup"] = random.choice(["a", "b"])
        files[PurePosixPath(f"s{number}.sec")] = _file("sequence", 300 + number, **fields)
    return files


def _engine(workspace: Workspace) -> Engine:
    document = compile_package(workspace).value
    assert document is not None
    package = read_package(PurePosixPath("p.json"), json.dumps(document).encode()).value
    assert package is not None
    return Engine(package)


@pytest.mark.parametrize("seed", range(400))
def test_the_engine_runs_and_asks_what_the_oracle_says(seed: int) -> None:
    random = Random(seed)  # noqa: S311 (a fixed seed: the same projects on every run)
    workspace = load_workspace(_project(random), PROFILES, MANIFESTS).value
    if workspace is None:
        return  # two clips overlap: not a project anyone can build
    timelines = timelines_of(workspace)
    engine = _engine(workspace)
    oracle: tuple[Running, ...] = ()
    now = 0

    for _ in range(12):
        now += random.choice([0, 250, 500, 1000, 3000])
        sequence = random.choice(SEQUENCES)
        if random.random() < 0.75:
            engine.start(sequence, now)
            oracle = start(oracle, Running(sequence, now), timelines)
        else:
            engine.stop(sequence)
            oracle = stop(still_running(oracle, now, timelines), sequence)
        change = engine.next_change_ms(now)
        until = now + 4000 if change is None else change
        # Just after the event, half way, and the instant before the next change: the same
        # throughout, and what the oracle says.
        asked_now = engine.asked(LED, now)
        for at_ms in sorted({now, (now + until) // 2, until - 1}):
            live = still_running(oracle, at_ms, timelines)
            assert [(run.sequence, run.started_ms) for run in engine.running(at_ms)] == [
                (run.sequence, run.started_ms) for run in live
            ], (seed, at_ms)
            expected = command_at(LED, at_ms, live, timelines)
            asked = engine.asked(LED, at_ms)
            assert (asked and (asked.command.clip, asked.since_ms)) == (
                expected and (expected.clip.id, expected.since_ms)
            ), (seed, at_ms)
            assert (asked and asked.command) == (asked_now and asked_now.command), (seed, at_ms)


def test_a_sequence_the_package_does_not_have_is_refused() -> None:
    workspace = load_workspace(_project(Random(1)), PROFILES, MANIFESTS).value  # noqa: S311
    assert workspace is not None
    engine = _engine(workspace)
    unknown = UUID(int=999)

    for ask in (lambda: engine.start(unknown, 0), lambda: engine.stop(unknown)):
        with pytest.raises(PrimumError) as refused:
            ask()
        assert (refused.value.code, dict(refused.value.params)) == (
            ErrorCode.SEQUENCE_UNKNOWN,
            {"id": str(unknown)},
        )


def test_with_nothing_running_nothing_is_asked_and_nothing_will_change() -> None:
    workspace = load_workspace(_project(Random(1)), PROFILES, MANIFESTS).value  # noqa: S311
    assert workspace is not None
    engine = _engine(workspace)

    assert engine.running(0) == ()
    assert engine.asked(LED, 0) is None
    assert engine.next_change_ms(0) is None
