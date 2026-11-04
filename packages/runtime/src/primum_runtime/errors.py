"""Errors raised by the runtime: a stable code and parameters, never text (decision 0009)."""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

type ErrorScalar = str | int | float | bool
# Lists are tuples of scalars; the UI formats them for the user's language ("17 and 27").
type ErrorParam = ErrorScalar | tuple[ErrorScalar, ...]


class ErrorCode(StrEnum):
    """Every code the runtime can raise. Each one has an entry in every ``i18n/`` catalog (a
    test checks it), so adding a code means adding its messages too. Codes are a public
    contract: renaming one is a breaking change.
    """

    HAL_PIN_IN_USE = "hal.pin_in_use"
    HAL_PIN_INVALID = "hal.pin_invalid"
    HAL_PIN_UNAVAILABLE = "hal.pin_unavailable"
    HAL_CHIP_UNAVAILABLE = "hal.chip_unavailable"
    HAL_CHIP_ACCESS_DENIED = "hal.chip_access_denied"
    HAL_UNSUPPORTED_PLATFORM = "hal.unsupported_platform"
    HAL_GPIO_LIBRARY_BROKEN = "hal.gpio_library_broken"
    HAL_CLOSED = "hal.closed"
    HAL_SAFE_STATE_INCOMPLETE = "hal.safe_state_incomplete"
    HAL_RELEASE_INCOMPLETE = "hal.release_incomplete"
    OUTPUT_UNKNOWN = "output.unknown"
    PANIC_ACTIVE = "panic.active"
    REQUEST_INVALID = "request.invalid"
    REQUEST_NOT_FOUND = "request.not_found"
    REQUEST_METHOD_NOT_ALLOWED = "request.method_not_allowed"


class PrimumError(Exception):
    """An error identified by a stable ``code`` (``<area>.<reason>``) and simple ``params``
    (scalars or tuples of scalars).

    The message shown to users and AI comes from the ``i18n/`` catalogs, keyed by ``code``.
    """

    def __init__(self, code: ErrorCode, params: Mapping[str, ErrorParam] | None = None) -> None:
        self.code = code
        self.params: Mapping[str, ErrorParam] = MappingProxyType(dict(params or {}))
        super().__init__(code, dict(self.params))

    def __str__(self) -> str:
        """``code (name=value, ...)`` for logs and tracebacks; users read the catalogs."""
        if not self.params:
            return self.code
        params = ", ".join(f"{name}={value}" for name, value in self.params.items())
        return f"{self.code} ({params})"
