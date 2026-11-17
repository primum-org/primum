"""Commands on named elements, with panic above them (decision 0006, layer 1).

The API and, later, the engine reach the elements through a ``Controller``, never through the
HAL. It makes a driver for each element, claims them all at once and keeps them by name. There
are no sequences or manual layer yet: a command goes straight to the driver of its output,
unless panic is active. Panic puts every output in its safe state and refuses commands until
it is released. Inputs are listened to: ``read_inputs`` takes their changes from the HAL.

Listeners are told the new ``State`` after every change; they must not block.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from primum_core.generated.model import Driver
from primum_core.values import Value
from primum_runtime.drivers import (
    DigitalInputDriver,
    ElementConfig,
    OptionLimits,
    OutputDriver,
    create_driver,
)
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.hal import Claim, Hal, InputSpec, OutputSpec, PwmSpec

type Listener = Callable[[State], None]

ON, OFF = "on", "off"


@dataclass(frozen=True)
class OutputState:
    """An output: its level, from 0 to 100, and whether that is on at all."""

    name: str
    on: bool
    level: float


@dataclass(frozen=True)
class InputState:
    name: str
    active: bool


@dataclass(frozen=True)
class State:
    """What the controller reports: every output and every input, in configuration order,
    and panic."""

    outputs: tuple[OutputState, ...]
    inputs: tuple[InputState, ...]
    panic: bool


class Controller:
    """Owns the elements claimed from one HAL, through their drivers, and the panic latch."""

    def __init__(
        self,
        hal: Hal,
        elements: Sequence[ElementConfig],
        manifests: Mapping[str, Driver],
        limits: OptionLimits,
    ) -> None:
        """Make the driver of every element and claim them all at once. Outputs start in
        their safe state.

        Fails, before anything is claimed, with what ``create_driver`` reports for an element
        (a type without a driver, an option its manifest or its board does not take); then
        with what the HAL reports for the claim. Two elements of one name are a mistake of
        the caller: ``ValueError``.
        """
        names = [element.name for element in elements]
        if len(set(names)) != len(names):
            raise ValueError(f"two elements have the same name: {names}")
        self._hal = hal
        drivers = [create_driver(element, manifests, limits) for element in elements]
        specs = [driver.spec for driver in drivers]
        hal.claim(
            Claim(
                outputs=[spec for spec in specs if isinstance(spec, OutputSpec)],
                inputs=[spec for spec in specs if isinstance(spec, InputSpec)],
                pwms=[spec for spec in specs if isinstance(spec, PwmSpec)],
            )
        )
        for driver in drivers:
            driver.bind(hal)
        self._outputs = {d.name: d for d in drivers if isinstance(d, OutputDriver)}
        self._inputs = {d.pin: d for d in drivers if isinstance(d, DigitalInputDriver)}
        self._panic = False
        self._listeners: list[Listener] = []

    def state(self) -> State:
        outputs = tuple(
            OutputState(name, driver.level > 0, driver.level)
            for name, driver in self._outputs.items()
        )
        inputs = tuple(InputState(driver.name, driver.active) for driver in self._inputs.values())
        return State(outputs, inputs, self._panic)

    def command(self, name: str, action: str, arguments: Mapping[str, Value] | None = None) -> None:
        """Ask output ``name`` for one of the actions of its driver, as an instant command.

        Fails with ``output.unknown`` (param ``name``), ``panic.active`` while panic is on, or
        what the driver reports for the action and its arguments.
        """
        output = self._outputs.get(name)
        if output is None:
            raise PrimumError(ErrorCode.OUTPUT_UNKNOWN, {"name": name})
        if self._panic:
            raise PrimumError(ErrorCode.PANIC_ACTIVE)
        output.command(action, arguments)
        self._notify()

    def set_output(self, name: str, on: bool) -> None:
        """Turn output ``name`` on or off: ``command`` with ``on`` or ``off``."""
        self.command(name, ON if on else OFF)

    def events_fd(self) -> int | None:
        """What to watch to know when ``read_inputs`` has something to read; ``None`` when
        there are no inputs."""
        return self._hal.events_fd()

    def read_inputs(self) -> None:
        """Take the changes of the inputs since the last call; never blocks. Listeners are
        told once, if any input changed."""
        changed = False
        for event in self._hal.read_events():
            changed |= self._inputs[event.pin].handle(event)
        if changed:
            self._notify()

    def panic(self) -> None:
        """Latch panic and put every output in its safe state.

        Panic is latched before the safe state is tried, so no command gets through even if
        some output fails; that failure is raised (``hal.safe_state_incomplete``).
        """
        self._panic = True
        try:
            self._hal.apply_safe_state()
        finally:
            self._notify()

    def release_panic(self) -> None:
        """Accept commands again. Outputs stay in their safe state until commanded."""
        if not self._panic:
            return
        self._panic = False
        self._notify()

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Call ``listener`` with the new state after every change; returns an unsubscribe."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _notify(self) -> None:
        state = self.state()
        for listener in tuple(self._listeners):
            listener(state)
