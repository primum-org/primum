"""The HAL for Linux boards, through the GPIO character device (libgpiod v2) and sysfs PWM.

This is the only module allowed to import ``gpiod`` (an architecture contract enforces it), and
it is imported lazily by ``create_hal``, so the rest of the runtime runs where ``gpiod`` is not
installed (macOS, Windows, CI jobs without it).
"""

from datetime import timedelta
from pathlib import Path

import gpiod
from gpiod.line import Bias, Direction, Edge, Value

from primum_runtime.errors import ErrorCode, ErrorParam, PrimumError
from primum_runtime.hal.base import (
    BoardGpio,
    Claim,
    Drivers,
    Hal,
    InputEvent,
    InputSpec,
    Pull,
)
from primum_runtime.hal.pwm_sysfs import SysfsPwmChannel, find_pwm_chip

CONSUMER = "primum"
DEVICES = Path("/dev")
BIAS = {Pull.UP: Bias.PULL_UP, Pull.DOWN: Bias.PULL_DOWN, Pull.NONE: Bias.DISABLED}


class GpiodLine:
    """One line of the board's request: an output written and read, or an input read."""

    def __init__(self, request: gpiod.LineRequest, offset: int) -> None:
        self._request = request
        self._offset = offset

    def write(self, active: bool) -> None:
        self._request.set_value(self._offset, Value.ACTIVE if active else Value.INACTIVE)

    def read(self) -> bool:
        return self._request.get_value(self._offset) == Value.ACTIVE


class GpiodHal(Hal):
    """Drives the GPIO lines of a board, on the chip its profile names by label, with one
    request for every line claimed (decision 0015), and its PWM channels through sysfs.

    The chip is found by label (``pinctrl-bcm2711`` on a Raspberry Pi 4) because its device
    number can change with the kernel. It is opened when the HAL is created and closed with it,
    so a wrong chip is reported as such and not as the first pin requested. Each GPIO is
    requested on the line the profile gives it, after checking that line is free; whatever
    ``request_lines`` raises after that means a line is unavailable.

    The kernel only knows the lines requested through the character device: programs that
    write ``/dev/gpiomem`` directly (RPi.GPIO, pigpio) own lines it reports as free.
    """

    def __init__(self, board: BoardGpio) -> None:
        super().__init__(board)
        self._chip, self._path, self._num_lines = _find_chip(board.chip_label)
        self._chip_open = True
        self._request: gpiod.LineRequest | None = None
        self._pins_by_line: dict[int, int] = {}
        self._channels: dict[int, SysfsPwmChannel] = {}

    def close(self) -> None:
        try:
            super().close()
        finally:
            if self._chip_open:
                self._chip_open = False
                self._chip.close()

    def _claim(self, claim: Claim) -> Drivers:
        config: dict[int, gpiod.LineSettings] = {}
        for spec in claim.outputs:
            config[self._line(spec.pin)] = gpiod.LineSettings(
                direction=Direction.OUTPUT, output_value=Value.INACTIVE, active_low=spec.active_low
            )
        for spec in claim.inputs:
            config[self._line(spec.pin)] = _input_settings(spec)
        channels = {spec.pin: self._board.pwm_channel(spec.pin) for spec in claim.pwms}
        if config:
            gpio_pins = [spec.pin for spec in (*claim.outputs, *claim.inputs)]
            self._request = self._request_lines(config, gpio_pins)
        if claim.pwms:
            chip = find_pwm_chip(self._board.pwm_device)
            for spec in claim.pwms:
                channel = channels[spec.pin]
                self._channels[spec.pin] = SysfsPwmChannel(
                    chip, channel, spec.pin, spec.frequency_hz
                )
        request = self._request
        lines = {
            spec.pin: GpiodLine(request, self._board.line(spec.pin))
            for spec in (*claim.outputs, *claim.inputs)
            if request is not None
        }
        return Drivers(
            outputs={spec.pin: lines[spec.pin] for spec in claim.outputs},
            inputs={spec.pin: lines[spec.pin] for spec in claim.inputs},
            pwms=dict(self._channels),
        )

    def _release(self) -> dict[int, Exception]:
        failures: dict[int, Exception] = {}
        if self._request is not None:
            try:
                self._request.release()
            except Exception as error:  # the PWM channels are still released
                failures.update(dict.fromkeys(self._pins_by_line.values(), error))
            self._request = None
        self._pins_by_line.clear()
        for pin, channel in self._channels.items():
            try:
                channel.release()
            except Exception as error:  # collected: the others are released too
                failures[pin] = error
        self._channels.clear()
        return failures

    def _read_events(self) -> list[InputEvent]:
        if self._request is None or not self._request.wait_edge_events(0):
            return []
        events = self._request.read_edge_events()
        return [
            InputEvent(
                self._pins_by_line[event.line_offset],
                event.event_type is gpiod.EdgeEvent.Type.RISING_EDGE,
                event.timestamp_ns,
            )
            for event in events
        ]

    def _wait_events(self, timeout_s: float) -> bool:
        if self._request is None:
            return False
        return self._request.wait_edge_events(timedelta(seconds=timeout_s))

    def _line(self, pin: int) -> int:
        """The chip line of ``pin``, checked against the chip and remembered by line."""
        line = self._board.line(pin)
        self._check_line(pin, line)
        self._pins_by_line[line] = pin
        return line

    def _request_lines(
        self, config: dict[int, gpiod.LineSettings], pins: list[int]
    ) -> gpiod.LineRequest:
        try:
            return self._chip.request_lines(
                {line: settings for line, settings in config.items()}, consumer=CONSUMER
            )
        except (OSError, ValueError) as error:
            # Another process may take a line after the check; gpiod raises ValueError(EINVAL)
            # for some lines the kernel owns, so the exception type says nothing more. The
            # request is all or nothing, so every pin is named.
            raise PrimumError(
                ErrorCode.HAL_PIN_UNAVAILABLE,
                {"pin": pins[0], "pins": tuple(pins), "chip": self._path, "detail": _detail(error)},
            ) from error

    def _check_line(self, pin: int, line: int) -> None:
        if line >= self._num_lines:
            # The pin exists on the board, but the profile puts it on a line this chip lacks:
            # the profile is wrong for this board, not the user's pin.
            raise PrimumError(
                ErrorCode.HAL_PROFILE_MISMATCH,
                {"pin": pin, "line": line, "chip": self._path, "lines": self._num_lines},
            )
        info = self._chip.get_line_info(line)
        if not info.used:
            return
        params: dict[str, ErrorParam] = {"pin": pin, "chip": self._path}
        # Lines held by kernel drivers (I2C, SPI…) report no consumer; gpioinfo prints "kernel"
        # for them, but an unlabelled userspace request looks the same, so nothing is guessed.
        if info.consumer:
            params["consumer"] = info.consumer
        raise PrimumError(ErrorCode.HAL_PIN_UNAVAILABLE, params)


def _input_settings(spec: InputSpec) -> gpiod.LineSettings:
    """An input that reports both edges, in logical terms (active-low is applied by gpiod)."""
    return gpiod.LineSettings(
        direction=Direction.INPUT,
        edge_detection=Edge.BOTH,
        bias=BIAS[spec.pull],
        active_low=spec.active_low,
        debounce_period=timedelta(milliseconds=spec.debounce_ms),
    )


def _chip_paths() -> list[str]:
    """Every GPIO chip device once: links (``gpiochip4 -> gpiochip0`` on Raspberry Pi OS, for
    programs written for a Pi 5) are skipped, as they name a chip that is already listed."""
    return sorted(str(path) for path in DEVICES.glob("gpiochip*") if not path.is_symlink())


def _find_chip(label: str) -> tuple[gpiod.Chip, str, int]:
    """Open the chip labelled ``label``: the chip, its device path and its number of lines.

    Every other chip is closed again, and one that cannot be opened or read is noted and
    skipped: another chip may still be the one. Only when none has the label does it fail,
    naming every chip and what happened to it, with ``hal.chip_access_denied`` if a chip
    could not be opened for lack of permission (it may be the one), ``hal.chip_not_found``
    otherwise.
    """
    found: list[str] = []
    denied: PermissionError | None = None
    for path in _chip_paths():
        try:
            chip = gpiod.Chip(path)
        except OSError as error:
            if isinstance(error, PermissionError):
                denied = error
            found.append(f"{path}: {_detail(error)}")
            continue
        try:
            info = chip.get_info()
        except OSError as error:
            chip.close()
            found.append(f"{path}: {_detail(error)}")
            continue
        if info.label == label:
            return chip, path, info.num_lines
        chip.close()
        found.append(f"{path} ({info.label})")
    detail = f"found {', '.join(found)}" if found else "no GPIO chip found"
    if denied is not None:
        raise PrimumError(
            ErrorCode.HAL_CHIP_ACCESS_DENIED, {"chip": label, "detail": detail}
        ) from denied
    raise PrimumError(ErrorCode.HAL_CHIP_NOT_FOUND, {"chip": label, "detail": detail})


def _detail(error: Exception) -> str:
    """The system's text for ``error`` (``strerror`` when there is one)."""
    if isinstance(error, OSError) and error.strerror:
        return error.strerror
    return str(error)
