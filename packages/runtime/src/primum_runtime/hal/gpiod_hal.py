"""The HAL for Linux boards, through the GPIO character device (libgpiod v2).

This is the only module allowed to import ``gpiod`` (an architecture contract enforces it), and
it is imported lazily by ``create_hal``, so the rest of the runtime runs where ``gpiod`` is not
installed (macOS, Windows, CI jobs without it).
"""

from pathlib import Path

import gpiod
from gpiod.line import Direction, Value

from primum_runtime.errors import ErrorCode, ErrorParam, PrimumError
from primum_runtime.hal.base import BoardGpio, Hal, OutputSpec

CONSUMER = "primum"
DEVICES = Path("/dev")


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
    """Drives the GPIO lines of a board, on the chip its profile names by label.

    The chip is found by label (``pinctrl-bcm2711`` on a Raspberry Pi 4) because its device
    number can change with the kernel. It is opened when the HAL is created and closed with it,
    so a wrong chip is reported as such and not as the first pin requested. Each GPIO is
    requested on the line the profile gives it, after checking that line is free; whatever
    ``request_lines`` raises after that means the line is unavailable.

    The kernel only knows the lines requested through the character device: programs that
    write ``/dev/gpiomem`` directly (RPi.GPIO, pigpio) own lines it reports as free.
    """

    def __init__(self, board: BoardGpio) -> None:
        super().__init__(board)
        self._chip, self._path, self._num_lines = _find_chip(board.chip_label)
        self._chip_open = True

    def close(self) -> None:
        try:
            super().close()
        finally:
            if self._chip_open:
                self._chip_open = False
                self._chip.close()

    def _open_line(self, spec: OutputSpec, line: int) -> GpiodLine:
        self._check_line(spec.pin, line)
        settings = gpiod.LineSettings(
            direction=Direction.OUTPUT,
            output_value=Value.INACTIVE,
            active_low=spec.active_low,
        )
        try:
            request = self._chip.request_lines({line: settings}, consumer=CONSUMER)
        except (OSError, ValueError) as error:
            # Another process may take the line after the check; gpiod raises ValueError(EINVAL)
            # for some lines the kernel owns, so the exception type says nothing more.
            raise PrimumError(
                ErrorCode.HAL_PIN_UNAVAILABLE,
                {"pin": spec.pin, "chip": self._path, "detail": _detail(error)},
            ) from error
        return GpiodLine(request, line)

    def _check_line(self, pin: int, line: int) -> None:
        if line >= self._num_lines:  # the profile and the chip disagree
            raise PrimumError(
                ErrorCode.HAL_PIN_INVALID,
                {"pin": pin, "chip": self._path, "lines": self._num_lines},
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


def _chip_paths() -> list[str]:
    return sorted(str(path) for path in DEVICES.glob("gpiochip*"))


def _find_chip(label: str) -> tuple[gpiod.Chip, str, int]:
    """Open the chip labelled ``label``: the chip, its device path and its number of lines.

    Every other chip opened on the way is closed. If no chip has the label, the error names the
    chips found, which tells a wrong board profile from missing permissions.
    """
    found: list[str] = []
    for path in _chip_paths():
        try:
            chip = gpiod.Chip(path)
        except OSError as error:
            if isinstance(error, PermissionError):
                raise _chip_error(label, error) from error
            found.append(f"{path}: {_detail(error)}")
            continue
        try:
            info = chip.get_info()
        except OSError as error:
            chip.close()
            raise _chip_error(label, error) from error
        if info.label == label:
            return chip, path, info.num_lines
        chip.close()
        found.append(f"{path} ({info.label})")
    detail = f"found {', '.join(found)}" if found else "no GPIO chip found"
    raise PrimumError(ErrorCode.HAL_CHIP_UNAVAILABLE, {"chip": label, "detail": detail})


def _chip_error(label: str, error: OSError) -> PrimumError:
    """No permission is its own code: the fix (joining group ``gpio``) differs."""
    if isinstance(error, PermissionError):
        code = ErrorCode.HAL_CHIP_ACCESS_DENIED
    else:
        code = ErrorCode.HAL_CHIP_UNAVAILABLE
    return PrimumError(code, {"chip": label, "detail": _detail(error)})


def _detail(error: Exception) -> str:
    """The system's text for ``error`` (``strerror`` when there is one)."""
    if isinstance(error, OSError) and error.strerror:
        return error.strerror
    return str(error)
