"""Resources of a board, given out to the elements wired to it: GPIOs, PWM channels, I2C buses.

Every board of a project (``.hw``) has a model with a board profile (``boards/``). The caller
loads the profiles (``core`` reads no files) and the allocator checks each element against the
profile of its board: the GPIO exists and is not reserved, nobody else has it, a PWM output sits
on a pin with hardware PWM and alone on its channel, an I2C device sits on a bus the board has
and alone at its address. A bus with a device on it claims the GPIOs of its signals, so an
element on them is reported as taken by the bus, not by another element.

Messages name pins as ``GPIO 17 (pin 11)``: the number elements use and where it is on the
header.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from uuid import UUID

from primum_core.boards import gpio_lines, physical_pins
from primum_core.errors import CoreErrorCode, Issue, Location, ParamValue
from primum_core.generated.model import BoardProfile, Bus, Element, Hardware
from primum_core.pointers import Step, pointer
from primum_core.references import LocatedContent

type Profiles = Mapping[str, BoardProfile]  # by model
type _Params = dict[str, ParamValue]

I2C_DEVICE = "i2c_device"
PWM_OUTPUT = "pwm_output"


@dataclass(frozen=True)
class _Wired:
    """An element on a board, and where it is declared: the file, and its steps inside."""

    element: Element
    location: Location
    steps: tuple[Step, ...]

    def at(self, *steps: Step) -> Location:
        return _at(self.location, *self.steps, *steps)


@dataclass
class _Board:
    """The resources of one board of the project, given out as its elements are checked."""

    name: str
    profile: BoardProfile
    gpios: Mapping[int, int] = field(init=False)  # GPIO → line (which GPIOs exist)
    physical: Mapping[int, int] = field(init=False)  # GPIO → physical pin
    reserved: frozenset[int] = field(init=False)
    pwm_channel_of: dict[int, str] = field(init=False)  # GPIO → channel id
    buses: dict[str, Bus] = field(init=False)
    taken: dict[int, str] = field(default_factory=dict[int, str])  # GPIO → element name
    taken_by_bus: dict[int, str] = field(default_factory=dict[int, str])  # GPIO → bus id
    channels: dict[str, str] = field(default_factory=dict[str, str])  # channel → element name
    addresses: dict[tuple[str, int], str] = field(default_factory=dict[tuple[str, int], str])

    def __post_init__(self) -> None:
        self.gpios = gpio_lines(self.profile)
        self.physical = physical_pins(self.profile)
        self.reserved = frozenset(entry.gpio for entry in self.profile.reserved)
        self.pwm_channel_of = {
            gpio: channel.id for channel in self.profile.pwm_channels for gpio in channel.gpios
        }
        self.buses = {bus.id: bus for bus in self.profile.buses if bus.kind == "i2c"}

    def pin_params(self, pin: int) -> _Params:
        return {"pin": pin, "physical": self.physical[pin]}


def check_resources(files: Iterable[LocatedContent], profiles: Profiles) -> tuple[Issue, ...]:
    """Every element that asks its board for something it does not have, or someone else has."""
    files = tuple(files)
    issues: list[Issue] = []
    boards = _boards(files, profiles, issues)
    wired = [
        (board, _Wired(element, file.location, ("elements", index)))
        for file in files
        if isinstance(file.content, Hardware)
        for index, element in enumerate(file.content.elements)
        if (board := boards.get(element.board)) is not None
    ]
    # Devices first: a bus with a device claims its GPIOs before any element asks for them.
    for board, device in wired:
        if device.element.type == I2C_DEVICE:
            issues += _i2c_issues(board, device)
    for board, element in wired:
        if element.element.type != I2C_DEVICE:
            issues += _gpio_issues(board, element)
    return tuple(issues)


def _at(location: Location, *steps: Step) -> Location:
    return replace(location, pointer=pointer(steps))


def _boards(
    files: tuple[LocatedContent, ...], profiles: Profiles, issues: list[Issue]
) -> dict[UUID, _Board]:
    """The project's boards by id, each with its profile; a model without one is reported."""
    boards: dict[UUID, _Board] = {}
    for file in files:
        if not isinstance(file.content, Hardware):
            continue
        for index, board in enumerate(file.content.boards):
            profile = profiles.get(board.model)
            if profile is None:
                params: _Params = {"model": board.model, "board": board.name}
                at = _at(file.location, "boards", index, "model")
                issues.append(Issue(CoreErrorCode.BOARD_UNKNOWN_MODEL, params, at))
            else:
                boards[board.id] = _Board(board.name, profile)
    return boards


def _i2c_issues(board: _Board, device: _Wired) -> Iterator[Issue]:
    element = device.element
    if element.bus is None or element.address is None:  # the variants check reports it
        return
    bus = board.buses.get(element.bus)
    if bus is None:
        params: _Params = {"bus": element.bus, "board": board.name}
        yield Issue(CoreErrorCode.BUS_NOT_ON_BOARD, params, device.at("bus"))
        return
    for signal in bus.signals:
        board.taken_by_bus.setdefault(signal.gpio, bus.id)
    other = board.addresses.get((bus.id, element.address))
    if other is not None:
        params = {"address": element.address, "bus": bus.id, "other": other}
        yield Issue(CoreErrorCode.I2C_ADDRESS_IN_USE, params, device.at("address"))
    else:
        board.addresses[(bus.id, element.address)] = element.name


def _gpio_issues(board: _Board, wired: _Wired) -> Iterator[Issue]:
    element = wired.element
    pin = element.pin
    if pin is None:  # the variants check reports it
        return
    at = wired.at("pin")
    if pin not in board.gpios:
        yield Issue(CoreErrorCode.PIN_NOT_ON_BOARD, {"pin": pin, "board": board.name}, at)
        return
    params = board.pin_params(pin)
    if pin in board.reserved:
        yield Issue(CoreErrorCode.PIN_RESERVED, params, at)
        return
    if pin in board.taken_by_bus:
        yield Issue(
            CoreErrorCode.PIN_CLAIMED_BY_BUS, {**params, "bus": board.taken_by_bus[pin]}, at
        )
        return
    other = board.taken.get(pin)
    if other is not None:
        yield Issue(CoreErrorCode.PIN_IN_USE, {**params, "other": other}, at)
        return
    board.taken[pin] = element.name
    if element.type == PWM_OUTPUT:
        yield from _pwm_issues(board, element, pin, at)


def _pwm_issues(board: _Board, element: Element, pin: int, at: Location) -> Iterator[Issue]:
    channel = board.pwm_channel_of.get(pin)
    params = board.pin_params(pin)
    if channel is None:
        yield Issue(CoreErrorCode.PIN_FUNCTION_UNAVAILABLE, params, at)
        return
    other = board.channels.get(channel)
    if other is not None:
        yield Issue(CoreErrorCode.PWM_CHANNEL_IN_USE, {**params, "other": other}, at)
    else:
        board.channels[channel] = element.name
