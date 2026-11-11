"""The hardware abstraction layer: the only way the runtime reaches hardware.

A ``Hal`` drives one board. The runtime claims everything it needs at once (``claim``): digital
outputs, digital inputs and hardware PWM outputs, so the real HAL makes one request per GPIO
chip (decision 0015). The safe state is guaranteed: every output starts in it, ``apply_safe_state``
returns all of them to it and reads them back to be sure (the line's level for a digital
output, the controller's setting for a PWM output), and ``close`` applies it before
releasing the lines, also when leaving a ``with`` block because of an exception. The safe state
of a digital output is *off* (inactive) and of a PWM output *0 %*; ``active_low`` only changes
which electrical level means *on*.

Inputs report their state on demand (``read``) and their changes as ``InputEvent``s with the
monotonic time each happened at (``read_events``), so a short press between two reads is seen.
The kernel keeps a bounded number of unread events and drops the oldest of a longer burst: the
state ``read`` gives is always right, a count of presses may not be.

Safety is best-effort across outputs: a failure on one line never stops the others from being
put in the safe state or released. The failures are reported together at the end.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType, TracebackType
from typing import Protocol, Self

from primum_runtime.errors import ErrorCode, PrimumError

log = logging.getLogger(__name__)


class Pull(StrEnum):
    """The resistor the board applies to an input when nothing drives it."""

    UP = "up"
    DOWN = "down"
    NONE = "none"


@dataclass(frozen=True)
class OutputSpec:
    """How a digital output is wired: its GPIO number (BCM) and whether it is active low.

    Whether the board has that GPIO is the HAL's to check, against the board profile.
    """

    pin: int
    active_low: bool = False


@dataclass(frozen=True)
class InputSpec:
    """How a digital input is wired: a button to ground is ``Pull.UP`` and active low.

    ``debounce_ms`` ignores bounces shorter than that; 0 leaves the signal as it is.
    """

    pin: int
    pull: Pull = Pull.UP
    active_low: bool = False
    debounce_ms: int = 0


@dataclass(frozen=True)
class PwmSpec:
    """A hardware PWM output: its GPIO and the frequency of the signal."""

    pin: int
    frequency_hz: int = 1000


@dataclass(frozen=True)
class Claim:
    """Everything the runtime asks of a board, claimed at once."""

    outputs: Sequence[OutputSpec] = ()
    inputs: Sequence[InputSpec] = ()
    pwms: Sequence[PwmSpec] = ()

    def pins(self) -> list[int]:
        return [spec.pin for spec in (*self.outputs, *self.inputs, *self.pwms)]


@dataclass(frozen=True)
class BoardGpio:
    """The GPIOs of a board, as its board profile describes them (``boards/<model>.json``).

    ``lines`` maps each GPIO number the board has to its line on the GPIO chip labelled
    ``chip_label``: a pin missing from it does not exist on this board. ``pwm_channels`` maps
    the GPIOs with hardware PWM to their channel on the controller ``pwm_device``.
    """

    model: str
    chip_label: str
    lines: Mapping[int, int]
    pwm_device: str = ""
    pwm_channels: Mapping[int, int] = field(default_factory=dict[int, int])

    def __post_init__(self) -> None:
        # Read-only copies: the board cannot change under a HAL that is using it.
        object.__setattr__(self, "lines", MappingProxyType(dict(self.lines)))
        object.__setattr__(self, "pwm_channels", MappingProxyType(dict(self.pwm_channels)))

    def line(self, pin: int) -> int:
        """The chip line of GPIO ``pin``; ``hal.pin_invalid`` if the board does not have it."""
        line = self.lines.get(pin)
        if line is None:
            raise PrimumError(ErrorCode.HAL_PIN_INVALID, {"pin": pin, "board": self.model})
        return line

    def pwm_channel(self, pin: int) -> int:
        """The PWM channel of GPIO ``pin``; ``hal.pwm_unsupported_pin`` if it has none."""
        self.line(pin)
        channel = self.pwm_channels.get(pin)
        if channel is None:
            raise PrimumError(ErrorCode.HAL_PWM_UNSUPPORTED_PIN, {"pin": pin, "board": self.model})
        return channel


@dataclass(frozen=True)
class InputEvent:
    """An input changed: to ``active`` or not, at ``timestamp_ns`` of the monotonic clock."""

    pin: int
    active: bool
    timestamp_ns: int


class LineDriver(Protocol):
    """One digital output line, requested in the safe (inactive) state."""

    def write(self, active: bool) -> None: ...

    def read(self) -> bool:
        """Logical state of the line as the hardware reports it (``True`` means active)."""
        ...


class InputDriver(Protocol):
    def read(self) -> bool:
        """Logical state of the input (``True`` means active)."""
        ...


class PwmDriver(Protocol):
    """One PWM channel, started at 0 %."""

    def write(self, duty: float) -> None: ...

    def read(self) -> float:
        """The duty cycle the hardware reports, 0 to 1."""
        ...


@dataclass(frozen=True)
class Drivers:
    """What an implementation gives back for a claim, by pin."""

    outputs: Mapping[int, LineDriver] = field(default_factory=dict[int, LineDriver])
    inputs: Mapping[int, InputDriver] = field(default_factory=dict[int, InputDriver])
    pwms: Mapping[int, PwmDriver] = field(default_factory=dict[int, PwmDriver])


class DigitalOutput:
    """An output that is either on or off."""

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

    def in_safe_state(self) -> bool:
        return not self.read()


class DigitalInput:
    """An input that is either active or not."""

    def __init__(self, spec: InputSpec, driver: InputDriver, hal: "Hal") -> None:
        self._spec = spec
        self._driver = driver
        self._hal = hal

    @property
    def spec(self) -> InputSpec:
        return self._spec

    def read(self) -> bool:
        """Read the input from the hardware (``True`` means active)."""
        self._hal.ensure_open()
        return self._driver.read()


class PwmOutput:
    """An output with a level from 0 (off) to 1 (fully on)."""

    def __init__(self, spec: PwmSpec, driver: PwmDriver, hal: "Hal") -> None:
        self._spec = spec
        self._driver = driver
        self._hal = hal
        self._duty = 0.0

    @property
    def spec(self) -> PwmSpec:
        return self._spec

    @property
    def duty(self) -> float:
        """The last level commanded successfully, 0 to 1."""
        return self._duty

    def read(self) -> float:
        """The level the controller is set to, 0 to 1: what the kernel reports for the channel,
        not a measurement of the pin, quantised to the period (the duty cycle is held in whole
        nanoseconds). Exactly 0.0 after ``set(0.0)``, which is what ``in_safe_state`` needs."""
        self._hal.ensure_open()
        return self._driver.read()

    def set(self, duty: float) -> None:
        """Set the level, 0 to 1; ``hal.duty_out_of_range`` otherwise."""
        self._hal.ensure_open()
        if not 0.0 <= duty <= 1.0:
            raise PrimumError(ErrorCode.HAL_DUTY_OUT_OF_RANGE, {"duty": duty})
        self._driver.write(duty)
        self._duty = duty

    def to_safe_state(self) -> None:
        self.set(0.0)

    def in_safe_state(self) -> bool:
        return self.read() == 0.0


type Output = DigitalOutput | PwmOutput


def _pins(failures: Mapping[int, Exception] | Sequence[int]) -> tuple[int, ...]:
    return tuple(sorted(failures))


def _not_safe(
    failures: Mapping[int, Exception], unverified: Sequence[int]
) -> dict[str, tuple[int, ...]]:
    """The params of a safe state with failed writes: ``pins`` names every output not confirmed
    safe, so nothing that may still be on is left out; ``unverified_pins`` says which of them
    were written but read back wrong."""
    params = {"pins": _pins([*failures, *unverified])}
    if unverified:
        params["unverified_pins"] = _pins(unverified)
    return params


def _incomplete(
    code: ErrorCode, params: dict[str, tuple[int, ...]], errors: Sequence[Exception]
) -> PrimumError:
    """One error naming the pins that failed, chained to every original exception."""
    error = PrimumError(code, params)
    if errors:
        error.__cause__ = ExceptionGroup(code, list(errors))
    return error


class Hal(ABC):
    """Base class of every HAL implementation (real hardware or simulated).

    A HAL drives one board: it only hands out pins its board profile lists, so the simulated
    HAL refuses the same pins the real one would.
    """

    def __init__(self, board: BoardGpio) -> None:
        self._board = board
        self._outputs: dict[int, DigitalOutput] = {}
        self._inputs: dict[int, DigitalInput] = {}
        self._pwms: dict[int, PwmOutput] = {}
        self._claimed = False
        self._closed = False

    @property
    def board(self) -> BoardGpio:
        return self._board

    @property
    def outputs(self) -> Mapping[int, DigitalOutput]:
        return MappingProxyType(self._outputs)

    @property
    def inputs(self) -> Mapping[int, DigitalInput]:
        return MappingProxyType(self._inputs)

    @property
    def pwms(self) -> Mapping[int, PwmOutput]:
        return MappingProxyType(self._pwms)

    def claim(self, claim: Claim) -> None:
        """Claim every line of ``claim`` at once; outputs start in the safe state.

        Fails with ``hal.already_claimed`` the second time, ``hal.pin_invalid`` for a GPIO the
        board does not have, ``hal.pin_in_use`` for a pin asked for twice and
        ``hal.pwm_unsupported_pin`` for a PWM output on a pin without hardware PWM and
        ``hal.pwm_channel_in_use`` for two PWM outputs on one channel (GPIO 12 and 18 on a
        Raspberry Pi: the controller has one channel for both). The implementation then reports
        the lines it cannot get; a claim that fails leaves nothing behind.
        """
        self.ensure_open()
        if self._claimed:
            raise PrimumError(ErrorCode.HAL_ALREADY_CLAIMED)
        seen: set[int] = set()
        for pin in claim.pins():
            self._board.line(pin)
            if pin in seen:
                raise PrimumError(ErrorCode.HAL_PIN_IN_USE, {"pin": pin})
            seen.add(pin)
        pin_by_channel: dict[int, int] = {}
        for spec in claim.pwms:
            channel = self._board.pwm_channel(spec.pin)
            other = pin_by_channel.setdefault(channel, spec.pin)
            if other != spec.pin:
                params = {"channel": channel, "pins": (other, spec.pin)}
                raise PrimumError(ErrorCode.HAL_PWM_CHANNEL_IN_USE, params)
        try:
            drivers = self._claim(claim)
        except Exception:
            self._release_after_failed_claim()
            raise
        self._claimed = True
        self._outputs = {
            spec.pin: DigitalOutput(spec, drivers.outputs[spec.pin], self) for spec in claim.outputs
        }
        self._inputs = {
            spec.pin: DigitalInput(spec, drivers.inputs[spec.pin], self) for spec in claim.inputs
        }
        self._pwms = {
            spec.pin: PwmOutput(spec, drivers.pwms[spec.pin], self) for spec in claim.pwms
        }

    def apply_safe_state(self) -> None:
        """Put every output in its safe state and read each one back, even if some fail.

        Raises ``hal.safe_state_incomplete`` after trying all of them if a write failed
        (``pins``: every output not confirmed safe; ``unverified_pins``: those among them whose
        write worked but read back wrong), else ``hal.safe_state_unverified`` (``pins``) if a
        line read back as not in its safe state: what the hardware reports is what matters, not
        what was written.
        """
        failures, unverified = self._safe_state_failures()
        if failures:
            code = ErrorCode.HAL_SAFE_STATE_INCOMPLETE
            raise _incomplete(code, _not_safe(failures, unverified), list(failures.values()))
        if unverified:
            raise PrimumError(ErrorCode.HAL_SAFE_STATE_UNVERIFIED, {"pins": _pins(unverified)})

    def read_events(self) -> list[InputEvent]:
        """The input changes since the last call, oldest first; never blocks. An implementation
        may stop after a bounded amount: what is left comes with the next call."""
        self.ensure_open()
        return self._read_events()

    def wait_events(self, timeout_s: float) -> bool:
        """Wait up to ``timeout_s`` for an input change; whether there is one to read."""
        self.ensure_open()
        return self._wait_events(timeout_s)

    def ensure_open(self) -> None:
        if self._closed:
            raise PrimumError(ErrorCode.HAL_CLOSED)

    def close(self) -> None:
        """Apply the safe state, then release every line; the HAL is closed afterwards.

        Every line is released even if putting some in the safe state or releasing others
        fails. At the end it raises ``hal.safe_state_incomplete`` (params as in
        ``apply_safe_state`` and, if releases failed too, ``release_pins``),
        ``hal.safe_state_unverified`` or
        ``hal.release_incomplete`` (param ``pins``), chained to the original exceptions. Closing
        twice does nothing.

        When a ``with`` block is left because of an exception and the safe state fails, the
        HAL's error replaces it; the original stays in ``__context__``. The failed safe state
        is what matters most then.

        Known limit: a second Ctrl+C while closing interrupts it (only ``Exception`` is
        collected). The watchdog and the safe-state unit of block 3.4 cover crashes.
        """
        if self._closed:
            return
        safe_failures, unverified = self._safe_state_failures()
        release_failures = self._release() if self._claimed else {}
        self._outputs.clear()
        self._inputs.clear()
        self._pwms.clear()
        self._closed = True

        errors = [*safe_failures.values(), *release_failures.values()]
        if safe_failures:
            params = _not_safe(safe_failures, unverified)
            if release_failures:
                params["release_pins"] = _pins(release_failures)
            raise _incomplete(ErrorCode.HAL_SAFE_STATE_INCOMPLETE, params, errors)
        if unverified:
            params = {"pins": _pins(unverified)}
            if release_failures:
                params["release_pins"] = _pins(release_failures)
            raise _incomplete(ErrorCode.HAL_SAFE_STATE_UNVERIFIED, params, errors)
        if release_failures:
            raise _incomplete(
                ErrorCode.HAL_RELEASE_INCOMPLETE, {"pins": _pins(release_failures)}, errors
            )

    def _release_after_failed_claim(self) -> None:
        """Release whatever the implementation got before failing halfway (a GPIO request made
        before a PWM channel was refused, for instance). A release that fails too is logged, not
        raised: the claim's error is the one to report."""
        for pin, error in self._release().items():
            log.warning("GPIO %d was not released after a failed claim: %s", pin, error)

    def _safe_state_failures(self) -> tuple[dict[int, Exception], list[int]]:
        """Put every output in its safe state; the writes that failed, and the pins that
        read back as not safe although their write succeeded."""
        failures: dict[int, Exception] = {}
        unverified: list[int] = []
        outputs: list[Output] = [*self._outputs.values(), *self._pwms.values()]
        for output in outputs:
            pin = output.spec.pin
            try:
                output.to_safe_state()
                if not output.in_safe_state():
                    unverified.append(pin)
            except Exception as error:  # collected and reported by the caller
                failures[pin] = error
        return failures, unverified

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
    def _claim(self, claim: Claim) -> Drivers:
        """Request every line of ``claim`` (pins already checked against the board), outputs in
        the inactive state and PWM outputs at 0 %."""

    @abstractmethod
    def _release(self) -> dict[int, Exception]:
        """Release everything claimed, or whatever a failed claim got; the failures by pin
        (every pin a failed release covers). Nothing to release is not a failure."""

    @abstractmethod
    def _read_events(self) -> list[InputEvent]: ...

    @abstractmethod
    def _wait_events(self, timeout_s: float) -> bool: ...
