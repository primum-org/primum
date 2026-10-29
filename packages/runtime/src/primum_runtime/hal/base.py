"""The hardware abstraction layer: the only way the runtime reaches hardware.

A ``Hal`` hands out outputs for pins and guarantees the safe state: every output starts in it,
``apply_safe_state`` returns all of them to it, and ``close`` applies it before releasing the
lines, also when leaving a ``with`` block because of an exception. The safe state of a digital
output is *off* (inactive); ``active_low`` only changes which electrical level means *on*.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol, Self

from primum_runtime.errors import PrimumError


@dataclass(frozen=True)
class OutputSpec:
    """How a digital output is wired: the GPIO line number and whether it is active low."""

    pin: int
    active_low: bool = False


class LineDriver(Protocol):
    """One requested hardware line. Implementations start it in the safe (inactive) state."""

    def write(self, active: bool) -> None: ...

    def release(self) -> None: ...


class DigitalOutput:
    """An output that is either on or off. Created by ``Hal.digital_output``."""

    def __init__(self, spec: OutputSpec, driver: LineDriver, hal: "Hal") -> None:
        self._spec = spec
        self._driver = driver
        self._hal = hal
        self._on = False

    @property
    def spec(self) -> OutputSpec:
        return self._spec

    @property
    def is_on(self) -> bool:
        return self._on

    def set(self, on: bool) -> None:
        """Turn the output on or off. Fails with ``hal.closed`` once the HAL is closed."""
        self._hal.ensure_open()
        self._driver.write(on)
        self._on = on

    def to_safe_state(self) -> None:
        self.set(False)


class Hal(ABC):
    """Base class of every HAL implementation (real hardware or simulated)."""

    def __init__(self) -> None:
        self._outputs: dict[int, DigitalOutput] = {}
        self._drivers: list[LineDriver] = []
        self._closed = False

    def digital_output(self, spec: OutputSpec) -> DigitalOutput:
        """Claim ``spec.pin`` as a digital output, starting in the safe state (off)."""
        self.ensure_open()
        if spec.pin in self._outputs:
            raise PrimumError("hal.pin_in_use", {"pin": spec.pin})
        driver = self._open_line(spec)
        self._drivers.append(driver)
        output = DigitalOutput(spec, driver, self)
        self._outputs[spec.pin] = output
        return output

    def apply_safe_state(self) -> None:
        """Put every output in its safe state."""
        for output in self._outputs.values():
            output.to_safe_state()

    def ensure_open(self) -> None:
        if self._closed:
            raise PrimumError("hal.closed")

    def close(self) -> None:
        """Apply the safe state, then release every line. Closing twice does nothing."""
        if self._closed:
            return
        try:
            self.apply_safe_state()
        finally:
            for driver in self._drivers:
                driver.release()
            self._drivers.clear()
            self._outputs.clear()
            self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @abstractmethod
    def _open_line(self, spec: OutputSpec) -> LineDriver:
        """Request the hardware line for ``spec``, already in the inactive state."""
