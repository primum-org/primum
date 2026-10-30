"""Commands on named outputs, with panic above them (decision 0006, layer 1).

The API and, later, the engine command outputs through a ``Controller``, never through the HAL.
Phase 1 has no sequences or manual layer yet: a command sets the output directly, unless panic
is active. Panic puts every output in its safe state and refuses commands until it is released.

Listeners are told the new ``State`` after every change; they must not block.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from primum_runtime.errors import PrimumError
from primum_runtime.hal import DigitalOutput, Hal, OutputSpec

type Listener = Callable[[State], None]


@dataclass(frozen=True)
class OutputState:
    name: str
    on: bool


@dataclass(frozen=True)
class State:
    """What the controller reports: every output, in configuration order, and panic."""

    outputs: tuple[OutputState, ...]
    panic: bool


class Controller:
    """Owns the outputs claimed from one HAL and the panic latch."""

    def __init__(self, hal: Hal, specs: Mapping[str, OutputSpec]) -> None:
        """Claim an output for every spec, by name. They start in the safe state (off)."""
        self._hal = hal
        self._outputs: dict[str, DigitalOutput] = {
            name: hal.digital_output(spec) for name, spec in specs.items()
        }
        self._panic = False
        self._listeners: list[Listener] = []

    def state(self) -> State:
        outputs = tuple(OutputState(name, output.is_on) for name, output in self._outputs.items())
        return State(outputs, self._panic)

    def set_output(self, name: str, on: bool) -> None:
        """Turn output ``name`` on or off.

        Fails with ``output.unknown`` (param ``name``) or ``panic.active`` while panic is on.
        """
        output = self._outputs.get(name)
        if output is None:
            raise PrimumError("output.unknown", {"name": name})
        if self._panic:
            raise PrimumError("panic.active")
        output.set(on)
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
