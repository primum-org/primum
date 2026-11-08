"""A HAL without hardware, for tests and for running the runtime on a laptop (``--simulate``)."""

from collections import deque
from collections.abc import Mapping
from types import MappingProxyType

from primum_runtime.hal.base import (
    BoardGpio,
    Claim,
    Drivers,
    Hal,
    InputEvent,
    InputSpec,
    OutputSpec,
    PwmSpec,
)


class SimulatedLine:
    """A simulated output line that remembers every value written to it.

    Faults can be injected to test what happens when the hardware misbehaves: ``fail_writes``,
    ``fail_release``, and ``stick(True)`` for a line that reads back on whatever is written.
    """

    def __init__(self, spec: OutputSpec) -> None:
        self._spec = spec
        self._active = False
        self._released = False
        self._history: list[bool] = []
        self._write_error: Exception | None = None
        self._release_error: Exception | None = None
        self._stuck: bool | None = None

    @property
    def active(self) -> bool:
        """Logical state: ``True`` means the output is on."""
        return self._active

    @property
    def level_high(self) -> bool:
        """Electrical level of the pin: an active-low output is low when on."""
        return self._active != self._spec.active_low

    @property
    def released(self) -> bool:
        return self._released

    @property
    def history(self) -> tuple[bool, ...]:
        """Every logical value written, in order (the initial safe state is not a write)."""
        return tuple(self._history)

    def fail_writes(self, error: Exception | None) -> None:
        """From now on every write raises ``error`` (``None`` makes writes work again)."""
        self._write_error = error

    def fail_release(self, error: Exception | None) -> None:
        """Make ``release`` raise ``error`` (``None`` makes it work again)."""
        self._release_error = error

    def stick(self, active: bool | None) -> None:
        """Make the line read back ``active`` whatever is written (``None`` unsticks it)."""
        self._stuck = active

    def write(self, active: bool) -> None:
        if self._write_error is not None:
            raise self._write_error
        self._active = active
        self._history.append(active)

    def read(self) -> bool:
        return self._active if self._stuck is None else self._stuck

    def release(self) -> None:
        if self._release_error is not None:
            raise self._release_error
        self._released = True


class SimulatedInput:
    """A simulated input: tests and the UI change it with ``SimulatedHal.simulate_input``."""

    def __init__(self, spec: InputSpec) -> None:
        self._spec = spec
        self.active = False

    def read(self) -> bool:
        return self.active


class SimulatedPwm:
    """A simulated PWM channel that remembers every level written to it."""

    def __init__(self, spec: PwmSpec) -> None:
        self._spec = spec
        self._duty = 0.0
        self._history: list[float] = []
        self._released = False

    @property
    def duty(self) -> float:
        return self._duty

    @property
    def history(self) -> tuple[float, ...]:
        return tuple(self._history)

    @property
    def released(self) -> bool:
        return self._released

    def write(self, duty: float) -> None:
        self._duty = duty
        self._history.append(duty)

    def read(self) -> float:
        return self._duty

    def release(self) -> None:
        self._released = True


class SimulatedHal(Hal):
    """A HAL whose lines live in memory, by pin. ``lines``, ``input_lines`` and ``pwm_lines``
    expose them to tests and to the UI.

    It takes the board profile like the real HAL, so ``--simulate`` refuses the pins the board
    does not have, as the Pi would. It has no clock: ``simulate_input`` takes the time of the
    change, and ``wait_events`` never waits.
    """

    def __init__(self, board: BoardGpio) -> None:
        super().__init__(board)
        self._lines: dict[int, SimulatedLine] = {}
        self._input_lines: dict[int, SimulatedInput] = {}
        self._pwm_lines: dict[int, SimulatedPwm] = {}
        self._events: deque[InputEvent] = deque()

    @property
    def lines(self) -> Mapping[int, SimulatedLine]:
        return MappingProxyType(self._lines)

    @property
    def input_lines(self) -> Mapping[int, SimulatedInput]:
        return MappingProxyType(self._input_lines)

    @property
    def pwm_lines(self) -> Mapping[int, SimulatedPwm]:
        return MappingProxyType(self._pwm_lines)

    def simulate_input(self, pin: int, active: bool, timestamp_ns: int = 0) -> None:
        """Change a claimed input from outside, as a button or a sensor would, and queue the
        event. Changes to the same state are not events, as on hardware."""
        line = self._input_lines[pin]
        if line.active == active:
            return
        line.active = active
        self._events.append(InputEvent(pin, active, timestamp_ns))

    def _claim(self, claim: Claim) -> Drivers:
        self._lines = {spec.pin: SimulatedLine(spec) for spec in claim.outputs}
        self._input_lines = {spec.pin: SimulatedInput(spec) for spec in claim.inputs}
        self._pwm_lines = {spec.pin: SimulatedPwm(spec) for spec in claim.pwms}
        return Drivers(dict(self._lines), dict(self._input_lines), dict(self._pwm_lines))

    def _release(self) -> dict[int, Exception]:
        failures: dict[int, Exception] = {}
        for pin, line in [*self._lines.items(), *self._pwm_lines.items()]:
            try:
                line.release()
            except Exception as error:  # collected: the others are released too
                failures[pin] = error
        return failures

    def _read_events(self) -> list[InputEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def _wait_events(self, timeout_s: float) -> bool:
        return bool(self._events)
