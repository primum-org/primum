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
    HAL_ALREADY_CLAIMED = "hal.already_claimed"
    HAL_PIN_INVALID = "hal.pin_invalid"
    HAL_PWM_UNSUPPORTED_PIN = "hal.pwm_unsupported_pin"
    HAL_PWM_CHANNEL_IN_USE = "hal.pwm_channel_in_use"
    HAL_PWM_NOT_ROUTED = "hal.pwm_not_routed"
    HAL_PWM_CHIP_NOT_FOUND = "hal.pwm_chip_not_found"
    HAL_PWM_UNAVAILABLE = "hal.pwm_unavailable"
    HAL_PWM_FREQUENCY_INVALID = "hal.pwm_frequency_invalid"
    HAL_DUTY_OUT_OF_RANGE = "hal.duty_out_of_range"
    HAL_PIN_UNAVAILABLE = "hal.pin_unavailable"
    HAL_REQUEST_FAILED = "hal.request_failed"
    HAL_PROFILE_MISMATCH = "hal.profile_mismatch"
    HAL_CHIP_NOT_FOUND = "hal.chip_not_found"
    HAL_CHIP_ACCESS_DENIED = "hal.chip_access_denied"
    HAL_UNSUPPORTED_PLATFORM = "hal.unsupported_platform"
    HAL_GPIO_LIBRARY_BROKEN = "hal.gpio_library_broken"
    HAL_CLOSED = "hal.closed"
    HAL_SAFE_STATE_INCOMPLETE = "hal.safe_state_incomplete"
    HAL_SAFE_STATE_UNVERIFIED = "hal.safe_state_unverified"
    HAL_RELEASE_INCOMPLETE = "hal.release_incomplete"
    ELEMENT_TYPE_UNSUPPORTED = "element.type_unsupported"
    ELEMENT_ACTIVE_LOW_UNSUPPORTED = "element.active_low_unsupported"
    ELEMENT_WIRING_REFUSED = "element.wiring_refused"
    ELEMENT_ACTION_UNKNOWN = "element.action_unknown"
    ELEMENT_VALUE_UNKNOWN = "element.value_unknown"
    ELEMENT_VALUE_MISSING = "element.value_missing"
    ELEMENT_VALUE_INVALID = "element.value_invalid"
    ELEMENT_VALUE_OUT_OF_RANGE = "element.value_out_of_range"
    ELEMENT_VALUE_UNLIMITED = "element.value_unlimited"
    ELEMENT_LEVEL_NOT_REACHED = "element.level_not_reached"
    ELEMENT_VARIABLE_UNFIT = "element.variable_unfit"
    PACKAGE_UNREADABLE = "package.unreadable"
    PACKAGE_INVALID = "package.invalid"
    PACKAGE_BOARD_UNSUPPORTED = "package.board_unsupported"
    PACKAGE_TIME_ZONE_UNKNOWN = "package.time_zone_unknown"
    PACKAGE_TOO_LARGE = "package.too_large"
    PACKAGE_UNWRITABLE = "package.unwritable"
    PACKAGE_NOT_STORED = "package.not_stored"
    PACKAGE_NO_PREVIOUS = "package.no_previous"
    PACKAGE_FIXED = "package.fixed"
    PACKAGE_ACTIVATION_FAILED = "package.activation_failed"
    PACKAGE_STOP_FAILED = "package.stop_failed"
    PAIRING_REQUIRED = "pairing.required"
    PAIRING_CODE_WRONG = "pairing.code_wrong"
    PAIRING_LOCKED = "pairing.locked"
    PAIRING_DEVICE_UNKNOWN = "pairing.device_unknown"
    PAIRING_OFF = "pairing.off"
    PAIRING_UNWRITABLE = "pairing.unwritable"
    SAFE_DECLARATION_UNWRITABLE = "safe.declaration_unwritable"
    SAFE_DECLARATION_INVALID = "safe.declaration_invalid"
    TEST_DURATION_OUT_OF_RANGE = "test.duration_out_of_range"
    OUTPUT_UNKNOWN = "output.unknown"
    SEQUENCE_UNKNOWN = "sequence.unknown"
    VARIABLE_UNKNOWN = "variable.unknown"
    VARIABLE_VALUE_INVALID = "variable.value_invalid"
    VARIABLE_VALUE_OUT_OF_RANGE = "variable.value_out_of_range"
    VARIABLES_UNWRITABLE = "variables.unwritable"
    EVENT_UNKNOWN = "event.unknown"
    EVENT_NOT_FIREABLE = "event.not_fireable"
    EVENT_NOT_LISTENABLE = "event.not_listenable"
    AUTOMATION_CONDITION_FAILED = "automation.condition_failed"
    AUTOMATION_ACTION_FAILED = "automation.action_failed"
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
