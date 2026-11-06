"""GENERATED from schemas/ by tools/gen_schemas.py: do not edit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from primum_core.json_values import JsonObject, as_choice, as_int, as_list, as_object, as_str, as_uuid


_HEADER_PIN_KIND: Final[tuple[Literal["gpio", "power_3v3", "power_5v", "ground"], ...]] = ("gpio", "power_3v3", "power_5v", "ground")
_HEADER_PIN_DEFAULT_PULL: Final[tuple[Literal["up", "down"], ...]] = ("up", "down")
_BUS_KIND: Final[tuple[Literal["i2c", "spi", "uart"], ...]] = ("i2c", "spi", "uart")
_RESERVED_GPIO_REASON: Final[tuple[Literal["hat_eeprom"], ...]] = ("hat_eeprom",)


@dataclass(frozen=True, kw_only=True, slots=True)
class BoardProfile:
    """What a board model offers: its header pins, buses, PWM channels and reserved pins, and how its GPIOs map to the lines of its GPIO chip. One file per model in boards/."""

    id: UUID
    kind: Literal["board_profile"] = "board_profile"
    schema_version: Literal[1] = 1
    model: str
    name: str
    gpio_chip: GpioChip
    pins: tuple[HeaderPin, ...]
    buses: tuple[Bus, ...]
    pwm_channels: tuple[PwmChannel, ...]
    reserved: tuple[ReservedGpio, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class GpioChip:
    """The GPIO chip that drives the header, found by its label: the device number (/dev/gpiochipN) can change with the kernel."""

    label: str


@dataclass(frozen=True, kw_only=True, slots=True)
class HeaderPin:
    """A pin of the header. A gpio pin has its GPIO number, its line on the GPIO chip and its pull at power on; other pins have none of them."""

    physical: int
    kind: Literal["gpio", "power_3v3", "power_5v", "ground"]
    gpio: int | None = None
    line: int | None = None
    default_pull: Literal["up", "down"] | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class Bus:
    id: str
    kind: Literal["i2c", "spi", "uart"]
    signals: tuple[BusSignal, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class BusSignal:
    name: str
    gpio: int


@dataclass(frozen=True, kw_only=True, slots=True)
class PwmChannel:
    id: str
    gpios: tuple[int, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class ReservedGpio:
    gpio: int
    reason: Literal["hat_eeprom"]


@dataclass(frozen=True, kw_only=True, slots=True)
class Project:
    """The manifest of a project: project.json, at the root of the project's folder."""

    id: UUID
    kind: Literal["project"] = "project"
    schema_version: Literal[1] = 1
    name: str
    description: str | None = None


def parse_board_profile(data: JsonObject) -> BoardProfile:
    """Build a ``BoardProfile`` from a document that passed its schema."""
    return BoardProfile(
        id=as_uuid(data["id"]),
        model=as_str(data["model"]),
        name=as_str(data["name"]),
        gpio_chip=parse_gpio_chip(as_object(data["gpioChip"])),
        pins=tuple(parse_header_pin(as_object(item)) for item in as_list(data["pins"])),
        buses=tuple(parse_bus(as_object(item)) for item in as_list(data["buses"])),
        pwm_channels=tuple(parse_pwm_channel(as_object(item)) for item in as_list(data["pwmChannels"])),
        reserved=tuple(parse_reserved_gpio(as_object(item)) for item in as_list(data["reserved"])),
    )


def parse_gpio_chip(data: JsonObject) -> GpioChip:
    """Build a ``GpioChip`` from a document that passed its schema."""
    return GpioChip(
        label=as_str(data["label"]),
    )


def parse_header_pin(data: JsonObject) -> HeaderPin:
    """Build a ``HeaderPin`` from a document that passed its schema."""
    return HeaderPin(
        physical=as_int(data["physical"]),
        kind=as_choice(data["kind"], _HEADER_PIN_KIND),
        gpio=as_int(data["gpio"]) if "gpio" in data else None,
        line=as_int(data["line"]) if "line" in data else None,
        default_pull=as_choice(data["defaultPull"], _HEADER_PIN_DEFAULT_PULL) if "defaultPull" in data else None,
    )


def parse_bus(data: JsonObject) -> Bus:
    """Build a ``Bus`` from a document that passed its schema."""
    return Bus(
        id=as_str(data["id"]),
        kind=as_choice(data["kind"], _BUS_KIND),
        signals=tuple(parse_bus_signal(as_object(item)) for item in as_list(data["signals"])),
    )


def parse_bus_signal(data: JsonObject) -> BusSignal:
    """Build a ``BusSignal`` from a document that passed its schema."""
    return BusSignal(
        name=as_str(data["name"]),
        gpio=as_int(data["gpio"]),
    )


def parse_pwm_channel(data: JsonObject) -> PwmChannel:
    """Build a ``PwmChannel`` from a document that passed its schema."""
    return PwmChannel(
        id=as_str(data["id"]),
        gpios=tuple(as_int(item) for item in as_list(data["gpios"])),
    )


def parse_reserved_gpio(data: JsonObject) -> ReservedGpio:
    """Build a ``ReservedGpio`` from a document that passed its schema."""
    return ReservedGpio(
        gpio=as_int(data["gpio"]),
        reason=as_choice(data["reason"], _RESERVED_GPIO_REASON),
    )


def parse_project(data: JsonObject) -> Project:
    """Build a ``Project`` from a document that passed its schema."""
    return Project(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        description=as_str(data["description"]) if "description" in data else None,
    )
