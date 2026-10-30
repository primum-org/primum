"""Hardware abstraction layer: the only way the runtime reaches hardware.

Use ``create_hal`` to get the real HAL on a board or the simulated one anywhere else, and keep it
in a ``with`` block so the safe state is applied when the runtime stops.
"""

import sys

from primum_runtime.errors import ErrorCode, PrimumError
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
    ``hal.unsupported_platform``; with a broken ``gpiod`` (part of it missing, for example its C
    extension ``gpiod._ext``), with ``hal.gpio_library_broken``.
    """
    if simulate:
        return SimulatedHal()
    # Imported here so that gpiod is only needed when driving real hardware.
    try:
        from primum_runtime.hal.gpiod_hal import DEFAULT_CHIP, GpiodHal
    except ImportError as error:
        mapped = _gpiod_import_error(error)
        if mapped is None:
            raise
        raise mapped from error

    return GpiodHal(chip or DEFAULT_CHIP)


def _gpiod_import_error(error: ImportError) -> PrimumError | None:
    """The error for a failed import of ``gpiod``, or ``None`` if the failure is not gpiod's."""
    if error.name is None or error.name.split(".")[0] != "gpiod":
        return None
    if isinstance(error, ModuleNotFoundError) and error.name == "gpiod":
        return PrimumError(ErrorCode.HAL_UNSUPPORTED_PLATFORM, {"platform": sys.platform})
    return PrimumError(ErrorCode.HAL_GPIO_LIBRARY_BROKEN, {"detail": str(error)})
