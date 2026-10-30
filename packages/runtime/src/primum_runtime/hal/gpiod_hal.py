"""The HAL for Linux boards, through the GPIO character device (libgpiod v2).

This is the only module allowed to import ``gpiod`` (an architecture contract enforces it), and
it is imported lazily by ``create_hal``, so the rest of the runtime runs where ``gpiod`` is not
installed (macOS, Windows, CI jobs without it).
"""

import gpiod
from gpiod.line import Direction, Value

from primum_runtime.errors import ErrorParam, PrimumError
from primum_runtime.hal.base import Hal, OutputSpec

DEFAULT_CHIP = "/dev/gpiochip0"
CONSUMER = "primum"


class GpiodLine:
    """One output line requested from the kernel, created in the inactive (safe) state."""

    def __init__(self, request: gpiod.LineRequest, offset: int) -> None:
        self._request = request
        self._offset = offset

    def write(self, active: bool) -> None:
        self._request.set_value(self._offset, Value.ACTIVE if active else Value.INACTIVE)

    def read(self) -> bool:
        return self._request.get_value(self._offset) == Value.ACTIVE

    def release(self) -> None:
        self._request.release()


class GpiodHal(Hal):
    """Drives GPIO lines of one chip. On a Raspberry Pi 4, line offsets are BCM numbers.

    The chip is opened when the HAL is created and closed with it, so a wrong chip is reported
    as such and not as the first pin requested. A pin is checked against the chip before it is
    requested; whatever ``request_lines`` raises after that means the line is unavailable.

    The kernel only knows the lines requested through the character device: programs that
    write ``/dev/gpiomem`` directly (RPi.GPIO, pigpio) own lines it reports as free.
    """

    def __init__(self, chip: str = DEFAULT_CHIP) -> None:
        super().__init__()
        self._path = chip
        self._chip, self._num_lines = _open_chip(chip)
        self._chip_open = True

    def close(self) -> None:
        try:
            super().close()
        finally:
            if self._chip_open:
                self._chip_open = False
                self._chip.close()

    def _open_line(self, spec: OutputSpec) -> GpiodLine:
        self._check_line(spec.pin)
        settings = gpiod.LineSettings(
            direction=Direction.OUTPUT,
            output_value=Value.INACTIVE,
            active_low=spec.active_low,
        )
        try:
            request = self._chip.request_lines({spec.pin: settings}, consumer=CONSUMER)
        except (OSError, ValueError) as error:
            # Another process may take the line after the check; gpiod raises ValueError(EINVAL)
            # for some lines the kernel owns, so the exception type says nothing more.
            raise PrimumError(
                "hal.pin_unavailable",
                {"pin": spec.pin, "chip": self._path, "detail": _detail(error)},
            ) from error
        return GpiodLine(request, spec.pin)

    def _check_line(self, pin: int) -> None:
        if pin >= self._num_lines:
            raise PrimumError(
                "hal.pin_invalid", {"pin": pin, "chip": self._path, "lines": self._num_lines}
            )
        info = self._chip.get_line_info(pin)
        if not info.used:
            return
        params: dict[str, ErrorParam] = {"pin": pin, "chip": self._path}
        # Lines held by kernel drivers (I2C, SPI…) report no consumer; gpioinfo prints "kernel"
        # for them, but an unlabelled userspace request looks the same, so nothing is guessed.
        if info.consumer:
            params["consumer"] = info.consumer
        raise PrimumError("hal.pin_unavailable", params)


def _open_chip(path: str) -> tuple[gpiod.Chip, int]:
    """Open the chip and read its number of lines; on failure, nothing is left open."""
    try:
        chip = gpiod.Chip(path)
    except OSError as error:
        raise _chip_error(path, error) from error
    try:
        return chip, chip.get_info().num_lines
    except OSError as error:
        chip.close()
        raise _chip_error(path, error) from error


def _chip_error(path: str, error: OSError) -> PrimumError:
    """No permission is its own code: the fix (joining group ``gpio``) differs."""
    if isinstance(error, PermissionError):
        code = "hal.chip_access_denied"
    else:
        code = "hal.chip_unavailable"
    return PrimumError(code, {"chip": path, "detail": _detail(error)})


def _detail(error: Exception) -> str:
    """The system's text for ``error`` (``strerror`` when there is one)."""
    if isinstance(error, OSError) and error.strerror:
        return error.strerror
    return str(error)
