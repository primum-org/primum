"""Drivers: each implements an element type on the HAL, as its manifest describes it.

``create_driver`` makes the driver of an element; ``load_manifests`` reads the manifests the
runtime ships (copies of ``drivers/``, made by ``just gen``).
"""

from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from primum_core.formats import read_drivers
from primum_core.generated.model import Driver
from primum_runtime.drivers.base import (
    ElementConfig,
    ElementDriver,
    OptionLimits,
    OutputDriver,
)
from primum_runtime.drivers.digital_input import DigitalInputDriver
from primum_runtime.drivers.digital_output import DigitalOutputDriver
from primum_runtime.drivers.pwm_output import PwmOutputDriver
from primum_runtime.errors import ErrorCode, PrimumError

__all__ = [
    "DRIVERS",
    "DigitalInputDriver",
    "DigitalOutputDriver",
    "ElementConfig",
    "ElementDriver",
    "OptionLimits",
    "OutputDriver",
    "PwmOutputDriver",
    "create_driver",
    "load_manifests",
]

MANIFESTS = Path(__file__).resolve().parent.parent / "generated" / "drivers"

# The implementation of each element type. One without an entry has no driver on this
# platform, whatever its manifest says.
DRIVERS: Mapping[str, type[ElementDriver]] = {
    "digital_output": DigitalOutputDriver,
    "digital_input": DigitalInputDriver,
    "pwm_output": PwmOutputDriver,
}


def load_manifests() -> Mapping[str, Driver]:
    """Every shipped driver manifest, by element type.

    They ship with Primum and are checked by its tests, so a broken one is a bug: it raises
    ``ValueError`` with the issues instead of a user-facing error.
    """
    files = {PurePosixPath(path.name): path.read_bytes() for path in MANIFESTS.glob("*.json")}
    parsed = read_drivers(files)
    if parsed.value is None:
        codes = ", ".join(f"{issue.code} ({issue.location})" for issue in parsed.issues)
        raise ValueError(f"invalid driver manifests in {MANIFESTS}: {codes}")
    return parsed.value


def create_driver(
    element: ElementConfig, manifests: Mapping[str, Driver], limits: OptionLimits
) -> ElementDriver:
    """The driver of ``element``, its options checked against its manifest and its board.

    Fails with ``element.type_unsupported`` for a type without a driver here, and with what
    ``values.resolve`` reports for the options.
    """
    implementation = DRIVERS.get(element.type)
    manifest = manifests.get(element.type)
    if implementation is None or manifest is None:
        params = {"element": element.name, "type": element.type}
        raise PrimumError(ErrorCode.ELEMENT_TYPE_UNSUPPORTED, params)
    return implementation(element, manifest, limits)
