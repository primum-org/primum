"""A small show for the tests of the engine on a board: its package, a controller running it
on the simulated HAL with a clock moved by hand, and the service with its API."""

import json
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from uuid import UUID

from fastapi.testclient import TestClient

from primum_core.compiler import compile_package
from primum_core.generated.model import Package
from primum_core.package import read_package
from primum_core.workspace import load_workspace
from primum_runtime.api import create_app
from primum_runtime.board import load_board, load_profile, option_limits
from primum_runtime.config import parse_config
from primum_runtime.control import Controller, State
from primum_runtime.drivers import load_manifests
from primum_runtime.hal import SimulatedHal
from primum_runtime.package import check_against_board

MANIFESTS = load_manifests()
PROFILE = load_profile("rpi4b")
LED, LAMP = str(UUID(int=4)), str(UUID(int=5))
LED_PIN, LAMP_PIN = 17, 18
# Sequences on the LED, and one on the lamp. Each by the number of its id.
BLINK, ON, OVER, DIM, UNKNOWN = (str(UUID(int=number)) for number in (20, 30, 40, 50, 99))
# Fades of the lamp.
GLOW, DOWN, RISE = (str(UUID(int=number)) for number in (70, 80, 90))
PULSE, SLOW_PULSE = str(UUID(int=110)), str(UUID(int=120))
HIGH, LOW = str(UUID(int=130)), str(UUID(int=140))
BRIGHTNESS, SPEED = str(UUID(int=61)), str(UUID(int=62))  # an integer, and a number
WAIT_S = 5  # for a second of a real service to pass: far more than it takes


def make_id(number: int) -> str:
    return str(UUID(int=number))


def make_file(kind: str, number: int, **fields: object) -> bytes:
    return json.dumps({"id": make_id(number), "kind": kind, "schemaVersion": 1, **fields}).encode()


def make_sequence(
    number: int, name: str, element: int, *clips: dict[str, object], **fields: object
) -> bytes:
    written = [{"id": make_id(number + index + 1), **clip} for index, clip in enumerate(clips)]
    tracks = [{"element": make_id(element), "clips": written}]
    return make_file("sequence", number, name=name, tracks=tracks, **fields)


def _fade(duration_ms: int, *arguments: dict[str, object]) -> dict[str, object]:
    clip: dict[str, object] = {"atMs": 0, "durationMs": duration_ms, "action": "fade"}
    return {**clip, "arguments": list(arguments)}


def _pulse(number: int, name: str, half_ms: int) -> bytes:
    """Up to 100 and straight back down, the way down without a ``from``."""
    up = _fade(half_ms, {"name": "from", "value": 0}, {"name": "to", "value": 100})
    down = {**_fade(half_ms, {"name": "to", "value": 0}), "atMs": half_ms}
    return make_sequence(number, name, 5, up, down)


def document() -> dict[str, object]:
    """A Pi with an LED and a lamp, and four sequences:

    - *Blink*: the LED on for a second, from 1 s to 2 s; then it ends;
    - *On*: the LED on, held until it is stopped;
    - *Over*: priority 5, the LED off for two seconds;
    - *Dim*: the lamp at ``brightness`` (60 to start with) for a second;
    - *Glow*: the lamp fades from 20 to 80 in two seconds, and holds;
    - *Down*: the lamp fades to 0 in a second, from where it is;
    - *Rise*: the lamp fades to ``brightness`` in a second, from where it is, and holds;
    - *Pulse*: the lamp fades from 0 to 100 in 100 ms, then to 0 from where it is in
      another 100 ms; *Slow pulse* does the same in a second each;
    - *High*: priority 5, the lamp fades from 0 to 100 in ten seconds;
    - *Low*: the lamp fades to 0 in twenty seconds, from where it is.
    """
    board = {"id": make_id(3), "name": "Pi", "model": "rpi4b"}
    wiring = {"board": make_id(3)}
    elements = [
        {"id": make_id(4), "name": "LED", "type": "digital_output", "pin": LED_PIN, **wiring},
        {"id": make_id(5), "name": "Lamp", "type": "pwm_output", "pin": LAMP_PIN, **wiring},
    ]
    brightness = {"id": make_id(61), "name": "brightness", "type": "integer", "initial": 60}
    limited = {**brightness, "min": 0, "max": 100, "setting": True}
    speed = {"id": make_id(62), "name": "speed", "type": "number", "initial": 1.5}
    variables = [limited, {**speed, "min": 0, "max": 10, "setting": True}]
    dim = {"atMs": 0, "durationMs": 1000, "action": "set"}
    files = {
        "project.json": make_file("project", 1, name="Arbiter"),
        "hardware.hw": make_file("hardware", 2, boards=[board], elements=elements),
        "shop.vars": make_file("variables", 60, constants=[], variables=variables),
        "blink.sec": make_sequence(
            20, "Blink", 4, {"atMs": 1000, "durationMs": 1000, "action": "on"}
        ),
        "on.sec": make_sequence(
            30, "On", 4, {"atMs": 0, "durationMs": 0, "action": "on"}, whenDone="hold"
        ),
        "over.sec": make_sequence(
            40, "Over", 4, {"atMs": 0, "durationMs": 2000, "action": "off"}, priority=5
        ),
        "dim.sec": make_sequence(
            50, "Dim", 5, {**dim, "arguments": [{"name": "level", "valueOf": "brightness"}]}
        ),
        "glow.sec": make_sequence(
            70,
            "Glow",
            5,
            _fade(2000, {"name": "from", "value": 20}, {"name": "to", "value": 80}),
            whenDone="hold",
        ),
        "down.sec": make_sequence(80, "Down", 5, _fade(1000, {"name": "to", "value": 0})),
        "pulse.sec": _pulse(110, "Pulse", 100),
        "slow.sec": _pulse(120, "Slow pulse", 1000),
        "high.sec": make_sequence(
            130,
            "High",
            5,
            _fade(10_000, {"name": "from", "value": 0}, {"name": "to", "value": 100}),
            priority=5,
        ),
        "low.sec": make_sequence(140, "Low", 5, _fade(20_000, {"name": "to", "value": 0})),
        "rise.sec": make_sequence(
            90, "Rise", 5, _fade(1000, {"name": "to", "valueOf": "brightness"}), whenDone="hold"
        ),
    }
    return compiled(files)


def compiled(files: dict[str, bytes]) -> dict[str, object]:
    """The deployment package of a project, given as its files by path."""
    loaded = load_workspace(
        {PurePosixPath(path): content for path, content in files.items()},
        {"rpi4b": PROFILE},
        MANIFESTS,
    )
    assert loaded.value is not None, loaded.issues
    document = compile_package(loaded.value).value
    assert document is not None
    return document


def package(of: dict[str, object] | None = None) -> Package:
    """The package of ``of``, a compiled document; of the show when none is given."""
    written = json.dumps(document() if of is None else of).encode()
    package = read_package(PurePosixPath("p.json"), written).value
    assert package is not None
    return package


class Clock:
    """A monotonic clock a test moves by hand."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class Service:
    """A controller running the package on a simulated board, its clock in the test's hand."""

    def __init__(self, loaded: Package | None = None) -> None:
        loaded = package() if loaded is None else loaded
        self.hal = SimulatedHal(load_board("rpi4b"))
        self.clock = Clock()
        self.controller = Controller(
            self.hal,
            check_against_board(loaded, MANIFESTS),
            MANIFESTS,
            option_limits(PROFILE),
            clock=self.clock,
            package=loaded,
        )
        self.states: list[State] = []
        self.controller.subscribe(self.states.append)

    def after(self, seconds: float) -> None:
        """Let ``seconds`` pass and wake the controller, as its timer would."""
        self.clock.now += seconds
        self.controller.expire()

    @property
    def led(self) -> bool:
        return self.hal.lines[LED_PIN].active

    @property
    def lamp(self) -> float:
        return self.hal.pwm_lines[LAMP_PIN].duty

    def by(self, output: str = LED) -> str | None:
        """Who commands an output, as the state says."""
        return next(o.controlled_by for o in self.controller.state().outputs if o.id == output)

    def running(self) -> list[str]:
        return [s.name for s in self.controller.state().sequences if s.running]


@contextmanager
def running(
    tmp_path: Path, of: dict[str, object] | None = None
) -> Generator[tuple[TestClient, SimulatedHal]]:
    """The service running the package (of the show, or ``of``), with its API, on a
    simulated board."""
    path = tmp_path / "show.package.json"
    path.write_text(json.dumps(document() if of is None else of), encoding="utf-8")
    config = parse_config(["--simulate", "--package", str(path)], {})
    hal = SimulatedHal(load_board("rpi4b"))
    with TestClient(create_app(config, open_hal=lambda: hal)) as client:
        yield client, hal
