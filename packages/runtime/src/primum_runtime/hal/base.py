"""The hardware abstraction layer: the only way the runtime reaches hardware.

A ``Hal`` hands out outputs for pins and guarantees the safe state: every output starts in it,
``apply_safe_state`` returns all of them to it, and ``close`` applies it before releasing the
lines, also when leaving a ``with`` block because of an exception. The safe state of a digital
output is *off* (inactive); ``active_low`` only changes which electrical level means *on*.

Safety is best-effort across outputs: a failure on one line never stops the others from being
put in the safe state or released. The failures are reported together at the end.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol, Self

from primum_runtime.errors import ErrorCode, PrimumError


@dataclass(frozen=True)
class OutputSpec:
    """How a digital output is wired: the GPIO line number and whether it is active low.

    A negative pin fails with ``hal.pin_invalid``, before any HAL sees it.
    """

    pin: int
    active_low: bool = False

    def __post_init__(self) -> None:
        if self.pin < 0:
            raise PrimumError(ErrorCode.HAL_PIN_INVALID, {"pin": self.pin})


class LineDriver(Protocol):
    """One requested hardware line. Implementations start it in the safe (inactive) state."""

    def write(self, active: bool) -> None: ...

    def read(self) -> bool:
        """Logical state of the line as the hardware reports it (``True`` means active)."""
        ...

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
        """The last state commanded successfully, not a reading of the hardware.

        If a write fails, this keeps the previous value. Use ``read`` for the real state.
        """
        return self._on

    def read(self) -> bool:
        """Read the output's state from the hardware (``True`` means on)."""
        self._hal.ensure_open()
        return self._driver.read()

    def set(self, on: bool) -> None:
        """Turn the output on or off. Fails with ``hal.closed`` once the HAL is closed."""
        self._hal.ensure_open()
        self._driver.write(on)
        self._on = on

    def to_safe_state(self) -> None:
        self.set(False)


def _pins(failures: dict[int, Exception]) -> tuple[int, ...]:
    return tuple(sorted(failures))


def _incomplete(
    code: ErrorCode, params: dict[str, tuple[int, ...]], errors: list[Exception]
) -> PrimumError:
    """One error naming the pins that failed, chained to every original exception."""
    error = PrimumError(code, params)
    error.__cause__ = ExceptionGroup(code, errors)
    return error


class Hal(ABC):
    """Base class of every HAL implementation (real hardware or simulated)."""

    def __init__(self) -> None:
        self._outputs: dict[int, DigitalOutput] = {}
        # Kept apart from the outputs: from phase 3 one driver (a request per chip) will serve
        # several outputs, and close() releases drivers, not outputs.
        self._drivers: dict[int, LineDriver] = {}
        self._closed = False

    def digital_output(self, spec: OutputSpec) -> DigitalOutput:
        """Claim ``spec.pin`` as a digital output, starting in the safe state (off)."""
        self.ensure_open()
        if spec.pin in self._outputs:
            raise PrimumError(ErrorCode.HAL_PIN_IN_USE, {"pin": spec.pin})
        driver = self._open_line(spec)
        self._drivers[spec.pin] = driver
        output = DigitalOutput(spec, driver, self)
        self._outputs[spec.pin] = output
        return output

    def apply_safe_state(self) -> None:
        """Put every output in its safe state, even if some of them fail.

        Raises ``hal.safe_state_incomplete`` (param ``pins``) after trying all of them.
        """
        failures = self._safe_state_failures()
        if failures:
            code = ErrorCode.HAL_SAFE_STATE_INCOMPLETE
            raise _incomplete(code, {"pins": _pins(failures)}, list(failures.values()))

    def ensure_open(self) -> None:
        if self._closed:
            raise PrimumError(ErrorCode.HAL_CLOSED)

    def close(self) -> None:
        """Apply the safe state, then release every line; the HAL is closed afterwards.

        Every line is released even if putting some in the safe state or releasing others
        fails. At the end it raises ``hal.safe_state_incomplete`` (params ``pins`` and, if
        releases failed too, ``release_pins``) or ``hal.release_incomplete`` (param ``pins``),
        chained to every original exception. Closing twice does nothing.

        When a ``with`` block is left because of an exception and the safe state fails, the
        HAL's error replaces it; the original stays in ``__context__``. The failed safe state
        is what matters most then.

        Known limit: a second Ctrl+C while closing interrupts it (only ``Exception`` is
        collected). Phase 1 drives LEDs only; the watchdog of phase 3 covers crashes.
        """
        if self._closed:
            return
        safe_failures = self._safe_state_failures()
        release_failures: dict[int, Exception] = {}
        for pin, driver in self._drivers.items():
            try:
                driver.release()
            except Exception as error:  # collected and re-raised below, after trying all
                release_failures[pin] = error
        self._drivers.clear()
        self._outputs.clear()
        self._closed = True

        errors = [*safe_failures.values(), *release_failures.values()]
        if safe_failures:
            params = {"pins": _pins(safe_failures)}
            if release_failures:
                params["release_pins"] = _pins(release_failures)
            raise _incomplete(ErrorCode.HAL_SAFE_STATE_INCOMPLETE, params, errors)
        if release_failures:
            raise _incomplete(
                ErrorCode.HAL_RELEASE_INCOMPLETE, {"pins": _pins(release_failures)}, errors
            )

    def _safe_state_failures(self) -> dict[int, Exception]:
        """Try to put every output in its safe state; return the failures by pin."""
        failures: dict[int, Exception] = {}
        for pin, output in self._outputs.items():
            try:
                output.to_safe_state()
            except Exception as error:  # collected and reported by the caller
                failures[pin] = error
        return failures

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
