"""Hardware abstraction layer: the only way the runtime reaches hardware.

Use ``create_hal`` to get the real HAL on a board or the simulated one anywhere else, and keep it
in a ``with`` block so the safe state is applied when the runtime stops.
"""

import sys

from primum_runtime.errors import PrimumError
from primum_runtime.hal.base import DigitalOutput, Hal, LineDriver, OutputSpec
from primum_runtime.hal.simulated import SimulatedHal, SimulatedLine

__all__ = [
    "DigitalOutput",
    "Hal",
    "LineDriver",
    "OutputSpec",
    "SimulatedHal",
    "SimulatedLine",
    "create_hal",
]


def create_hal(*, simulate: bool, chip: str | None = None) -> Hal:
    """Return a simulated HAL, or the GPIO HAL for ``chip`` (default ``/dev/gpiochip0``).

    Without ``gpiod`` (it is installed on Linux only) the GPIO HAL fails with
    ``hal.unsupported_platform``.
    """
    if simulate:
        return SimulatedHal()
    # Imported here so that gpiod is only needed when driving real hardware.
    try:
        from primum_runtime.hal.gpiod_hal import DEFAULT_CHIP, GpiodHal
    except ModuleNotFoundError as error:
        if error.name != "gpiod":
            raise
        raise PrimumError("hal.unsupported_platform", {"platform": sys.platform}) from error

    return GpiodHal(chip or DEFAULT_CHIP)
