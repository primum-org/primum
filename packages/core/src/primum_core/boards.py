"""Board profiles: what a profile means beyond its schema, and what others ask of it.

A profile (``boards/<model>.json``) describes a board model as data. Its schema checks the
shape; this module checks what the shape cannot say: each physical pin and each GPIO appears
once, a GPIO pin has its number, line and pull while power pins have none, and buses, PWM
channels and reserved pins name GPIOs the board has. Callers read the file and use
``primum_core.formats.read_board_profile``, which runs these checks.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import replace

from primum_core.errors import CoreErrorCode, Issue, Location, ParamValue
from primum_core.generated.model import BoardProfile, HeaderPin


def check_board_profile(profile: BoardProfile, location: Location) -> tuple[Issue, ...]:
    """Every problem of meaning in ``profile``, pointing inside the file at ``location``."""
    return (*_pin_issues(profile.pins, location), *_reference_issues(profile, location))


def gpio_lines(profile: BoardProfile) -> Mapping[int, int]:
    """The line of each GPIO on the board's GPIO chip, by GPIO number."""
    return {
        pin.gpio: pin.line for pin in profile.pins if pin.gpio is not None and pin.line is not None
    }


def _pin_issues(pins: tuple[HeaderPin, ...], location: Location) -> Iterator[Issue]:
    physical: set[int] = set()
    gpios: set[int] = set()
    lines: set[int] = set()
    for index, pin in enumerate(pins):
        at = replace(location, pointer=f"/pins/{index}")
        if pin.physical in physical:
            yield Issue(CoreErrorCode.BOARD_DUPLICATE_PIN, {"physical": pin.physical}, at)
        physical.add(pin.physical)
        gpio_fields = (pin.gpio, pin.line, pin.default_pull)
        if pin.kind != "gpio":
            if any(value is not None for value in gpio_fields):
                yield Issue(CoreErrorCode.BOARD_POWER_PIN_WITH_GPIO, {"physical": pin.physical}, at)
            continue
        if pin.gpio is None or pin.line is None or pin.default_pull is None:
            yield Issue(CoreErrorCode.BOARD_INCOMPLETE_GPIO_PIN, {"physical": pin.physical}, at)
            continue
        yield from _once(CoreErrorCode.BOARD_DUPLICATE_GPIO, "gpio", pin.gpio, gpios, at)
        yield from _once(CoreErrorCode.BOARD_DUPLICATE_LINE, "line", pin.line, lines, at)


def _reference_issues(profile: BoardProfile, location: Location) -> Iterator[Issue]:
    # Every GPIO a pin names, complete or not: an incomplete pin is reported once, by itself.
    gpios = {pin.gpio for pin in profile.pins if pin.gpio is not None}
    references: list[tuple[int, str]] = []
    for bus_index, bus in enumerate(profile.buses):
        for index, signal in enumerate(bus.signals):
            references.append((signal.gpio, f"/buses/{bus_index}/signals/{index}/gpio"))
    for channel_index, channel in enumerate(profile.pwm_channels):
        for index, gpio in enumerate(channel.gpios):
            references.append((gpio, f"/pwmChannels/{channel_index}/gpios/{index}"))
    for index, reserved in enumerate(profile.reserved):
        references.append((reserved.gpio, f"/reserved/{index}/gpio"))
    for gpio, pointer in references:
        if gpio not in gpios:
            at = replace(location, pointer=pointer)
            yield Issue(CoreErrorCode.BOARD_UNKNOWN_GPIO, {"gpio": gpio}, at)
    yield from _unique_ids("buses", (bus.id for bus in profile.buses), location)
    yield from _unique_ids(
        "pwmChannels", (channel.id for channel in profile.pwm_channels), location
    )


def _unique_ids(field: str, ids: Iterable[str], location: Location) -> Iterator[Issue]:
    seen: set[str] = set()
    for index, identifier in enumerate(ids):
        at = replace(location, pointer=f"/{field}/{index}/id")
        yield from _once(CoreErrorCode.BOARD_DUPLICATE_ID, "id", identifier, seen, at)


def _once[T: ParamValue](
    code: CoreErrorCode, param: str, value: T, seen: set[T], at: Location
) -> Iterator[Issue]:
    """An issue if ``value`` was already seen; remembers it either way."""
    if value in seen:
        yield Issue(code, {param: value}, at)
    seen.add(value)
