"""A HAL without hardware, for tests and for running the runtime on a laptop (``--simulate``)."""

from collections.abc import Mapping
from types import MappingProxyType

from primum_runtime.hal.base import Hal, OutputSpec


class SimulatedLine:
    """A simulated output line that remembers every value written to it."""

    def __init__(self, spec: OutputSpec) -> None:
        self._spec = spec
        self._active = False
        self._released = False
        self._history: list[bool] = []

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

    def write(self, active: bool) -> None:
        self._active = active
        self._history.append(active)

    def release(self) -> None:
        self._released = True


class SimulatedHal(Hal):
    """A HAL whose lines live in memory. ``lines`` exposes them to tests and to the UI."""

    def __init__(self) -> None:
        super().__init__()
        self._lines: dict[int, SimulatedLine] = {}

    @property
    def lines(self) -> Mapping[int, SimulatedLine]:
        return MappingProxyType(self._lines)

    def _open_line(self, spec: OutputSpec) -> SimulatedLine:
        line = SimulatedLine(spec)
        self._lines[spec.pin] = line
        return line
