"""The controller against a simple model, on random orders.

The model is the three layers as the documentation says them (panic, then a person, then
the sequences, then rest), with an engine of its own to say what the sequences ask: the
engine is held to ``core`` elsewhere (``test_engine.py``). The service is woken only when its
own ``next_expiry_s`` says, as its timer does, so an instant it forgets to ask for shows as
an output left where it should not be.
"""

from dataclasses import dataclass, field
from random import Random
from uuid import UUID

import pytest

from primum_runtime.control import MANUAL, SEQUENCE, TEST
from primum_runtime.engine import Engine
from primum_runtime.errors import ErrorCode, PrimumError
from show_service import BLINK, DIM, LAMP, LED, ON, OVER, Service, package

# Sequences that ask for a fixed level: no fades, and nobody changes a variable here.
SEQUENCES = (BLINK, ON, OVER, DIM)
OUTPUTS = (LED, LAMP)
MS_PER_S = 1000
START_MS = 100_000
STEPS = 60
WAITS_MS = (0, 1, 250, 500, 999, 1000, 1001, 1500, 2000, 4000)
TESTS_MS = (1000, 1500, 3000)
MAX_WAKES = 200  # per wait: far more than any of these sequences needs


@dataclass
class _Model:
    """What the outputs should be at, worked out the simple way."""

    engine: Engine = field(default_factory=lambda: Engine(package()))
    panic: bool = False
    held: dict[str, tuple[float, int | None]] = field(
        default_factory=dict[str, tuple[float, int | None]]
    )

    def forget_expired(self, now_ms: int) -> None:
        self.held = {
            key: (level, until)
            for key, (level, until) in self.held.items()
            if until is None or until > now_ms
        }

    def level(self, key: str, now_ms: int) -> float:
        if self.panic:
            return 0
        if key in self.held:
            return self.held[key][0]
        asked = self.engine.asked(UUID(key), now_ms)
        return 0 if asked is None else _level(asked.command.action)

    def controlled_by(self, key: str, now_ms: int) -> str | None:
        if self.panic:
            return None
        if key in self.held:
            return MANUAL if self.held[key][1] is None else TEST
        return None if self.engine.asked(UUID(key), now_ms) is None else SEQUENCE


def _level(action: str) -> float:
    """The level each action of these sequences asks for: ``set`` is Dim's, at the initial
    brightness."""
    return {"on": 100.0, "off": 0.0, "set": 60.0}[action]


class _Run:
    """One service and its model, taking the same orders."""

    def __init__(self) -> None:
        self.service = Service()
        self.model = _Model()
        self.now_ms = START_MS
        self.service.clock.now = START_MS / MS_PER_S
        self.log: list[str] = []

    def order(self, random: Random) -> None:
        kind = random.choice(
            ["command", "command", "test", "release", "start", "start", "stop", "panic", "calm"]
        )
        controller = self.service.controller
        if kind in {"command", "test"}:
            key = random.choice(OUTPUTS)
            action, arguments, level = self._action(key, random)
            duration = random.choice(TESTS_MS) if kind == "test" else None
            self.log.append(f"{kind} {key[-2:]} {action} {arguments} {duration}")
            if self.model.panic:
                with pytest.raises(PrimumError) as refused:
                    controller.command(key, action, arguments, duration)
                assert refused.value.code is ErrorCode.PANIC_ACTIVE
                return
            controller.command(key, action, arguments, duration)
            until = None if duration is None else self.now_ms + duration
            self.model.held[key] = (level, until)
        elif kind == "release":
            key = random.choice(OUTPUTS)
            self.log.append(f"release {key[-2:]}")
            controller.release(key)
            self.model.held.pop(key, None)
        elif kind == "start":
            sequence = random.choice(SEQUENCES)
            self.log.append(f"start {sequence[-2:]}")
            if self.model.panic:
                with pytest.raises(PrimumError) as refused:
                    controller.start_sequence(sequence)
                assert refused.value.code is ErrorCode.PANIC_ACTIVE
                return
            controller.start_sequence(sequence)
            self.model.engine.start(UUID(sequence), self.now_ms)
        elif kind == "stop":
            sequence = random.choice(SEQUENCES)
            self.log.append(f"stop {sequence[-2:]}")
            controller.stop_sequence(sequence)
            self.model.engine.stop(UUID(sequence))
        elif kind == "panic":
            self.log.append("panic")
            controller.panic()
            self.model.panic = True
            self.model.held.clear()
            self.model.engine.stop_all()
        else:
            self.log.append("release panic")
            controller.release_panic()
            self.model.panic = False

    def _action(self, key: str, random: Random) -> tuple[str, dict[str, float], float]:
        if key == LAMP and random.random() < 0.5:
            level = float(random.choice([0, 10, 55, 100]))
            return "set", {"level": level}, level
        action = random.choice(["on", "off"])
        return action, {}, 100.0 if action == "on" else 0.0

    def wait(self, wait_ms: int) -> None:
        """Let time pass as the service lives it: woken when it asked to be, and only then."""
        self.log.append(f"wait {wait_ms}")
        target = self.now_ms + wait_ms
        for _ in range(MAX_WAKES):
            due = self.service.controller.next_expiry_s()
            wake = None if due is None else self.now_ms + max(0, round(due * MS_PER_S))
            if wake is None or wake > target:
                break
            self._move_to(wake)
            self.service.controller.expire()
            self.check()
        else:
            pytest.fail(f"the service asked to be woken over {MAX_WAKES} times: {self.log}")
        self._move_to(target)

    def _move_to(self, now_ms: int) -> None:
        self.now_ms = now_ms
        self.service.clock.now = now_ms / MS_PER_S
        self.model.forget_expired(now_ms)

    def check(self) -> None:
        service, model, now = self.service, self.model, self.now_ms
        state = service.controller.state()
        by_id = {output.id: output for output in state.outputs}
        expected = {key: model.level(key, now) for key in OUTPUTS}
        assert service.led is (expected[LED] > 0), self.log
        assert service.lamp == pytest.approx(expected[LAMP] / 100), self.log  # a duty, 0 to 1
        assert {key: by_id[key].level for key in OUTPUTS} == pytest.approx(expected), self.log
        assert {key: by_id[key].controlled_by for key in OUTPUTS} == {
            key: model.controlled_by(key, now) for key in OUTPUTS
        }, self.log
        assert {key: by_id[key].remaining_ms for key in OUTPUTS} == {
            key: None if (until := model.held.get(key, (0, None))[1]) is None else until - now
            for key in OUTPUTS
        }, self.log
        running = {str(run.sequence) for run in model.engine.running(now)}
        assert {s.id for s in state.sequences if s.running} == running, self.log
        assert state.panic is model.panic, self.log
        assert not any(output.rest_failed for output in state.outputs), self.log


@pytest.mark.parametrize("seed", range(300))
def test_random_orders_leave_every_output_where_the_layers_say(seed: int) -> None:
    random = Random(seed)  # noqa: S311 (a fixed seed: the same orders on every run)
    run = _Run()
    for _ in range(STEPS):
        if random.random() < 0.4:
            run.wait(random.choice(WAITS_MS))
        else:
            run.order(random)
        run.check()
