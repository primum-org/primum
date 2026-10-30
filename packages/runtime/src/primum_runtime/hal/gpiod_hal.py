"""The HAL for Linux boards, through the GPIO character device (libgpiod v2).

This is the only module allowed to import ``gpiod`` (an architecture contract enforces it), and
it is imported lazily by ``create_hal``, so the rest of the runtime runs where ``gpiod`` is not
installed (macOS, Windows, CI jobs without it).
"""

import gpiod
from gpiod.line import Direction, Value

from primum_runtime.errors import PrimumError
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
    """Drives GPIO lines of one chip. On a Raspberry Pi 4, line offsets are BCM numbers."""

    def __init__(self, chip: str = DEFAULT_CHIP) -> None:
        super().__init__()
        self._chip = chip

    def _open_line(self, spec: OutputSpec) -> GpiodLine:
        settings = gpiod.LineSettings(
            direction=Direction.OUTPUT,
            output_value=Value.INACTIVE,
            active_low=spec.active_low,
        )
        try:
            request = gpiod.request_lines(
                self._chip, consumer=CONSUMER, config={spec.pin: settings}
            )
        except ValueError as error:
            # gpiod rejects offsets the chip does not have ("line offset out of range").
            raise PrimumError(
                "hal.pin_invalid", {"pin": spec.pin, "chip": self._chip, "detail": str(error)}
            ) from error
        except OSError as error:
            raise PrimumError(
                "hal.pin_unavailable",
                {"pin": spec.pin, "chip": self._chip, "detail": error.strerror or str(error)},
            ) from error
        return GpiodLine(request, spec.pin)
