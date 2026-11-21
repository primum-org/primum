"""GENERATED from schemas/ by tools/gen_schemas.py: do not edit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from primum_core.json_values import JsonObject, as_bool, as_choice, as_float, as_int, as_list, as_object, as_scalar, as_str, as_uuid


_AUTOMATION_ACTION_ACTION: Final[tuple[Literal["start_sequence", "stop_sequence", "set_variable", "increment_variable"], ...]] = ("start_sequence", "stop_sequence", "set_variable", "increment_variable")
_HEADER_PIN_KIND: Final[tuple[Literal["gpio", "power_3v3", "power_5v", "ground"], ...]] = ("gpio", "power_3v3", "power_5v", "ground")
_HEADER_PIN_DEFAULT_PULL: Final[tuple[Literal["up", "down"], ...]] = ("up", "down")
_BUS_KIND: Final[tuple[Literal["i2c", "spi", "uart"], ...]] = ("i2c", "spi", "uart")
_RESERVED_GPIO_REASON: Final[tuple[Literal["hat_eeprom"], ...]] = ("hat_eeprom",)
_DRIVER_CONFLICT_POLICY: Final[tuple[Literal["latest_wins", "exclusive"], ...]] = ("latest_wins", "exclusive")
_DRIVER_PARAMETER_TYPE: Final[tuple[Literal["number", "integer", "boolean", "text"], ...]] = ("number", "integer", "boolean", "text")
_EVENT_SOURCE: Final[tuple[Literal["element", "ui", "api"], ...]] = ("element", "ui", "api")
_EVENT_TRIGGER: Final[tuple[Literal["on", "off"], ...]] = ("on", "off")
_ELEMENT_TYPE: Final[tuple[Literal["digital_output", "digital_input", "pwm_output", "i2c_device"], ...]] = ("digital_output", "digital_input", "pwm_output", "i2c_device")
_PACKAGE_VARIABLE_TYPE: Final[tuple[Literal["number", "integer", "boolean", "text"], ...]] = ("number", "integer", "boolean", "text")
_PACKAGE_SEQUENCE_WHEN_DONE: Final[tuple[Literal["end", "hold"], ...]] = ("end", "hold")
_PACKAGE_SEQUENCE_WHEN_STARTED_AGAIN: Final[tuple[Literal["restart", "ignore"], ...]] = ("restart", "ignore")
_PACKAGE_EVENT_SOURCE: Final[tuple[Literal["element", "ui", "api"], ...]] = ("element", "ui", "api")
_PACKAGE_EVENT_TRIGGER: Final[tuple[Literal["on", "off"], ...]] = ("on", "off")
_PACKAGE_TIME_DAYS: Final[tuple[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"], ...]] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_PACKAGE_WINDOW_DAYS: Final[tuple[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"], ...]] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_PACKAGE_ACTION_ACTION: Final[tuple[Literal["start_sequence", "stop_sequence", "set_variable", "increment_variable"], ...]] = ("start_sequence", "stop_sequence", "set_variable", "increment_variable")
_SCHEDULE_TIME_DAYS: Final[tuple[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"], ...]] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_SCHEDULE_WINDOW_DAYS: Final[tuple[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"], ...]] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_SEQUENCE_WHEN_DONE: Final[tuple[Literal["end", "hold"], ...]] = ("end", "hold")
_SEQUENCE_WHEN_STARTED_AGAIN: Final[tuple[Literal["restart", "ignore"], ...]] = ("restart", "ignore")
_PARAMETER_TYPE: Final[tuple[Literal["element", "number", "integer", "boolean", "text"], ...]] = ("element", "number", "integer", "boolean", "text")
_CONSTANT_TYPE: Final[tuple[Literal["number", "integer", "boolean", "text"], ...]] = ("number", "integer", "boolean", "text")
_VARIABLE_TYPE: Final[tuple[Literal["number", "integer", "boolean", "text"], ...]] = ("number", "integer", "boolean", "text")


@dataclass(frozen=True, kw_only=True, slots=True)
class Automation:
    """An .auto file: when an event or a schedule fires, if the condition holds, do the actions."""

    id: UUID
    kind: Literal["automation"] = "automation"
    schema_version: Literal[1] = 1
    name: str
    enabled: bool = True
    when: tuple[UUID, ...]
    if_: str | None = None
    do: tuple[AutomationAction, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class AutomationAction:
    """Start or stop a sequence, or set or increment a variable."""

    action: Literal["start_sequence", "stop_sequence", "set_variable", "increment_variable"]
    sequence: UUID | None = None
    variable: str | None = None
    value: float | bool | str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class BoardProfile:
    """What a board model offers: its header pins, buses, PWM channels and reserved pins, how its GPIOs map to the lines of its GPIO chip, and the limits it puts on the options of its elements. One file per model in boards/."""

    id: UUID
    kind: Literal["board_profile"] = "board_profile"
    schema_version: Literal[1] = 1
    model: str
    name: str
    gpio_chip: GpioChip
    pwm_chip: PwmChip
    pins: tuple[HeaderPin, ...]
    buses: tuple[Bus, ...]
    pwm_channels: tuple[PwmChannel, ...]
    reserved: tuple[ReservedGpio, ...]
    limits: tuple[OptionLimit, ...]


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
    channel: int
    gpios: tuple[int, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class ReservedGpio:
    gpio: int
    reason: Literal["hat_eeprom"]


@dataclass(frozen=True, kw_only=True, slots=True)
class PwmChip:
    """The hardware PWM controller, found by its device name in the kernel (the directory /sys/class/pwm/pwmchipN/device points at): the chip number can change with the kernel."""

    device: str


@dataclass(frozen=True, kw_only=True, slots=True)
class OptionLimit:
    """The values this board takes for one option of the elements of one type (the frequency of a PWM output), and where that is documented."""

    element_type: str
    option: str
    min: float
    max: float
    sources: tuple[str, ...]
    note: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class NamedValue:
    """A value given by name: an argument of a clip's action, an option of an element's configuration."""

    name: str
    value: float | bool | str


@dataclass(frozen=True, kw_only=True, slots=True)
class Driver:
    """What a driver offers, as data: the element type it serves, what a clip may ask of it and how the element is set up. One file per element type in drivers/. Its implementation lives in the runtimes."""

    id: UUID
    kind: Literal["driver"] = "driver"
    schema_version: Literal[1] = 1
    element_type: str
    conflict_policy: Literal["latest_wins", "exclusive"] | None = None
    safe_state: str | None = None
    config: tuple[DriverParameter, ...]
    actions: tuple[DriverAction, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class DriverAction:
    """An action of the element, with the parameters a clip gives it and the state it leaves the element in."""

    name: str
    parameters: tuple[DriverParameter, ...]
    end_state: float | str
    start_state: float | str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class DriverParameter:
    """A parameter of an action or an option of an element's configuration: its type, its limits and the value it takes when not given. Without a default it must be given, unless it is optional."""

    name: str
    type: Literal["number", "integer", "boolean", "text"]
    min: float | None = None
    max: float | None = None
    choices: tuple[str, ...] = ()
    default: float | bool | str | None = None
    optional: bool = False


@dataclass(frozen=True, kw_only=True, slots=True)
class Event:
    """An .evt file: something that happens outside and can start automations. The source says where it comes from: an input element, a button of the phone UI, or a request to the local API."""

    id: UUID
    kind: Literal["event"] = "event"
    schema_version: Literal[1] = 1
    name: str
    source: Literal["element", "ui", "api"]
    element: UUID | None = None
    trigger: Literal["on", "off"] | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class Hardware:
    """A .hw file: boards and the elements wired to them. Which resources an element uses depends on its type: a pin for GPIO elements, a bus and an address for I2C devices."""

    id: UUID
    kind: Literal["hardware"] = "hardware"
    schema_version: Literal[1] = 1
    name: str | None = None
    boards: tuple[HardwareBoard, ...]
    elements: tuple[Element, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class HardwareBoard:
    """A board of the project, of a model that has a board profile (boards/)."""

    id: UUID
    name: str
    model: str


@dataclass(frozen=True, kw_only=True, slots=True)
class Element:
    """Something wired to a board: an LED, a relay, a button, a sensor."""

    id: UUID
    name: str
    board: UUID
    type: Literal["digital_output", "digital_input", "pwm_output", "i2c_device"]
    pin: int | None = None
    active_low: bool = False
    bus: str | None = None
    address: int | None = None
    config: tuple[NamedValue, ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class Package:
    """A deployment package: a project compiled for one board, flat, built from a project that passed every check (decision 0024). Whoever reads one checks it again: its shape, its hash and that it holds together. It is all the runtime sees: no folders, no scopes, no components, no constants. Built by primum-core, never written by hand."""

    kind: Literal["package"] = "package"
    schema_version: Literal[1] = 1
    hash: str
    project: PackageProject
    board: PackageBoard
    elements: tuple[PackageElement, ...]
    variables: tuple[PackageVariable, ...]
    sequences: tuple[PackageSequence, ...]
    events: tuple[PackageEvent, ...]
    schedules: tuple[PackageSchedule, ...]
    automations: tuple[PackageAutomation, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class PackageProject:
    """The project the package was compiled from."""

    id: UUID
    name: str


@dataclass(frozen=True, kw_only=True, slots=True)
class PackageBoard:
    """The board the package is for."""

    id: UUID
    name: str
    model: str


@dataclass(frozen=True, kw_only=True, slots=True)
class PackageElement:
    """An element of the board, with every option of its driver: the ones its .hw file gives and the defaults of the others."""

    id: UUID
    name: str
    type: str
    pin: int | None = None
    active_low: bool = False
    bus: str | None = None
    address: int | None = None
    config: tuple[NamedValue, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class PackageVariable:
    """A variable: a value that changes while running."""

    id: UUID
    name: str
    type: Literal["number", "integer", "boolean", "text"]
    initial: float | bool | str
    min: float | None = None
    max: float | None = None
    persistent: bool
    setting: bool


@dataclass(frozen=True, kw_only=True, slots=True)
class PackageSequence:
    """A sequence that can be started: its components expanded, its clips turned into commands by the rule of decision 0017."""

    id: UUID
    name: str
    priority: int
    exclusive_group: str | None = None
    when_done: Literal["end", "hold"]
    when_started_again: Literal["restart", "ignore"]
    duration_ms: int
    commands: tuple[Command, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class Command:
    """What an element is asked from atMs, in the time of its sequence. In force until untilMs; without it, until the sequence is stopped (what a sequence that holds keeps). The action lasts durationMs, 0 for an instant command; after that the element stays in the state the action ends in."""

    clip: UUID
    element: UUID
    at_ms: int
    duration_ms: int
    until_ms: int | None = None
    action: str
    arguments: tuple[CommandArgument, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class CommandArgument:
    """The value of one parameter of the action: the value itself, or the variable to read it from while running (when exactly is the engine's). One of the two. Every parameter is here, the driver's default included, except an optional one that was left out."""

    name: str
    value: float | bool | str | None = None
    variable: UUID | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class PackageEvent:
    """Something that happens outside and starts automations."""

    id: UUID
    name: str
    source: Literal["element", "ui", "api"]
    element: UUID | None = None
    trigger: Literal["on", "off"] | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class PackageSchedule:
    """Times of day and windows of time that start automations."""

    id: UUID
    name: str
    times: tuple[PackageTime, ...]
    windows: tuple[PackageWindow, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class PackageTime:
    """Every listed day at a time."""

    days: tuple[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"], ...]
    at: str


@dataclass(frozen=True, kw_only=True, slots=True)
class PackageWindow:
    """Every listed day from one time to another."""

    days: tuple[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"], ...]
    from_: str
    to: str


@dataclass(frozen=True, kw_only=True, slots=True)
class PackageAutomation:
    """When an event or a schedule fires, if the condition holds, do the actions."""

    id: UUID
    name: str
    enabled: bool
    when: tuple[UUID, ...]
    if_: str | None = None
    do: tuple[PackageAction, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class PackageAction:
    """Start or stop a sequence, or set or increment a variable, each by its id."""

    action: Literal["start_sequence", "stop_sequence", "set_variable", "increment_variable"]
    sequence: UUID | None = None
    variable: UUID | None = None
    value: float | bool | str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class Project:
    """The manifest of a project: project.json, at the root of the project's folder."""

    id: UUID
    kind: Literal["project"] = "project"
    schema_version: Literal[1] = 1
    name: str
    description: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class Schedule:
    """A .sched file: times of day and windows of time that start automations. A time fires at its instant, and is lost if the board was off then; a window fires when it opens, or when the engine starts inside it (decision 0023). Windows are also conditions of automations."""

    id: UUID
    kind: Literal["schedule"] = "schedule"
    schema_version: Literal[1] = 1
    name: str
    times: tuple[ScheduleTime, ...] = ()
    windows: tuple[ScheduleWindow, ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class ScheduleTime:
    """Every listed day at a time."""

    days: tuple[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"], ...]
    at: str


@dataclass(frozen=True, kw_only=True, slots=True)
class ScheduleWindow:
    """Every listed day from one time to another."""

    days: tuple[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"], ...]
    from_: str
    to: str


@dataclass(frozen=True, kw_only=True, slots=True)
class Sequence:
    """A .sec file: actions placed in time on tracks, one track per element, and blocks that include other sequences. With parameters it is a component, reused by other sequences. Sequences never emit events."""

    id: UUID
    kind: Literal["sequence"] = "sequence"
    schema_version: Literal[1] = 1
    name: str
    description: str | None = None
    priority: int = 0
    exclusive_group: str | None = None
    when_done: Literal["end", "hold"] = "end"
    when_started_again: Literal["restart", "ignore"] = "restart"
    parameters: tuple[Parameter, ...] = ()
    tracks: tuple[Track, ...]
    blocks: tuple[Block, ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class Parameter:
    """An input of a component, given by each sequence that uses it."""

    id: UUID
    name: str
    type: Literal["element", "number", "integer", "boolean", "text"]


@dataclass(frozen=True, kw_only=True, slots=True)
class Track:
    """The clips of one element: an element of a .hw file, or an element parameter of this sequence."""

    element: UUID
    clips: tuple[Clip, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class Clip:
    """An action of the element from atMs: held for durationMs, or, with durationMs 0, an instant command, in force until the next instant command of the element in this sequence or the end of this sequence, of its block when it is included (decision 0017)."""

    id: UUID
    at_ms: int
    duration_ms: int
    action: str
    arguments: tuple[ClipArgument, ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class ClipArgument:
    """The value of one parameter of the clip's action: written here, or taken from a name (valueOf). One of the two."""

    name: str
    value: float | bool | str | None = None
    value_of: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class Block:
    """Another sequence, started at atMs."""

    id: UUID
    sequence: UUID
    at_ms: int
    arguments: tuple[Argument, ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class Argument:
    """The value of one parameter of the included sequence: an element for an element parameter; for the others a value, written (value) or taken from a name (valueOf)."""

    parameter: UUID
    element: UUID | None = None
    value: float | bool | str | None = None
    value_of: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class Variables:
    """A .vars file: the constants and variables of the folder it is in, and the names that folder shares with others (decision 0005)."""

    id: UUID
    kind: Literal["variables"] = "variables"
    schema_version: Literal[1] = 1
    constants: tuple[Constant, ...]
    variables: tuple[Variable, ...]
    exports: tuple[str, ...] = ()
    imports: tuple[VariableImport, ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class Constant:
    """A value fixed while the show runs, resolved when the project is compiled."""

    id: UUID
    name: str
    type: Literal["number", "integer", "boolean", "text"]
    value: float | bool | str


@dataclass(frozen=True, kw_only=True, slots=True)
class Variable:
    """A value that changes while running, owned by one board."""

    id: UUID
    name: str
    type: Literal["number", "integer", "boolean", "text"]
    initial: float | bool | str
    min: float | None = None
    max: float | None = None
    persistent: bool = False
    setting: bool = False


@dataclass(frozen=True, kw_only=True, slots=True)
class VariableImport:
    """A name exported by the .vars file of another folder."""

    from_: UUID
    name: str


def parse_automation(data: JsonObject) -> Automation:
    """Build a ``Automation`` from a document that passed its schema."""
    return Automation(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        enabled=as_bool(data["enabled"]) if "enabled" in data else True,
        when=tuple(as_uuid(item) for item in as_list(data["when"])),
        if_=as_str(data["if"]) if "if" in data else None,
        do=tuple(parse_automation_action(as_object(item)) for item in as_list(data["do"])),
    )


def parse_automation_action(data: JsonObject) -> AutomationAction:
    """Build a ``AutomationAction`` from a document that passed its schema."""
    return AutomationAction(
        action=as_choice(data["action"], _AUTOMATION_ACTION_ACTION),
        sequence=as_uuid(data["sequence"]) if "sequence" in data else None,
        variable=as_str(data["variable"]) if "variable" in data else None,
        value=as_scalar(data["value"]) if "value" in data else None,
    )


def parse_board_profile(data: JsonObject) -> BoardProfile:
    """Build a ``BoardProfile`` from a document that passed its schema."""
    return BoardProfile(
        id=as_uuid(data["id"]),
        model=as_str(data["model"]),
        name=as_str(data["name"]),
        gpio_chip=parse_gpio_chip(as_object(data["gpioChip"])),
        pwm_chip=parse_pwm_chip(as_object(data["pwmChip"])),
        pins=tuple(parse_header_pin(as_object(item)) for item in as_list(data["pins"])),
        buses=tuple(parse_bus(as_object(item)) for item in as_list(data["buses"])),
        pwm_channels=tuple(parse_pwm_channel(as_object(item)) for item in as_list(data["pwmChannels"])),
        reserved=tuple(parse_reserved_gpio(as_object(item)) for item in as_list(data["reserved"])),
        limits=tuple(parse_option_limit(as_object(item)) for item in as_list(data["limits"])),
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
        channel=as_int(data["channel"]),
        gpios=tuple(as_int(item) for item in as_list(data["gpios"])),
    )


def parse_reserved_gpio(data: JsonObject) -> ReservedGpio:
    """Build a ``ReservedGpio`` from a document that passed its schema."""
    return ReservedGpio(
        gpio=as_int(data["gpio"]),
        reason=as_choice(data["reason"], _RESERVED_GPIO_REASON),
    )


def parse_pwm_chip(data: JsonObject) -> PwmChip:
    """Build a ``PwmChip`` from a document that passed its schema."""
    return PwmChip(
        device=as_str(data["device"]),
    )


def parse_option_limit(data: JsonObject) -> OptionLimit:
    """Build a ``OptionLimit`` from a document that passed its schema."""
    return OptionLimit(
        element_type=as_str(data["elementType"]),
        option=as_str(data["option"]),
        min=as_float(data["min"]),
        max=as_float(data["max"]),
        sources=tuple(as_str(item) for item in as_list(data["sources"])),
        note=as_str(data["note"]) if "note" in data else None,
    )


def parse_named_value(data: JsonObject) -> NamedValue:
    """Build a ``NamedValue`` from a document that passed its schema."""
    return NamedValue(
        name=as_str(data["name"]),
        value=as_scalar(data["value"]),
    )


def parse_driver(data: JsonObject) -> Driver:
    """Build a ``Driver`` from a document that passed its schema."""
    return Driver(
        id=as_uuid(data["id"]),
        element_type=as_str(data["elementType"]),
        conflict_policy=as_choice(data["conflictPolicy"], _DRIVER_CONFLICT_POLICY) if "conflictPolicy" in data else None,
        safe_state=as_str(data["safeState"]) if "safeState" in data else None,
        config=tuple(parse_driver_parameter(as_object(item)) for item in as_list(data["config"])),
        actions=tuple(parse_driver_action(as_object(item)) for item in as_list(data["actions"])),
    )


def parse_driver_action(data: JsonObject) -> DriverAction:
    """Build a ``DriverAction`` from a document that passed its schema."""
    return DriverAction(
        name=as_str(data["name"]),
        parameters=tuple(parse_driver_parameter(as_object(item)) for item in as_list(data["parameters"])),
        end_state=as_scalar(data["endState"]),
        start_state=as_scalar(data["startState"]) if "startState" in data else None,
    )


def parse_driver_parameter(data: JsonObject) -> DriverParameter:
    """Build a ``DriverParameter`` from a document that passed its schema."""
    return DriverParameter(
        name=as_str(data["name"]),
        type=as_choice(data["type"], _DRIVER_PARAMETER_TYPE),
        min=as_float(data["min"]) if "min" in data else None,
        max=as_float(data["max"]) if "max" in data else None,
        choices=tuple(as_str(item) for item in as_list(data["choices"])) if "choices" in data else (),
        default=as_scalar(data["default"]) if "default" in data else None,
        optional=as_bool(data["optional"]) if "optional" in data else False,
    )


def parse_event(data: JsonObject) -> Event:
    """Build a ``Event`` from a document that passed its schema."""
    return Event(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        source=as_choice(data["source"], _EVENT_SOURCE),
        element=as_uuid(data["element"]) if "element" in data else None,
        trigger=as_choice(data["trigger"], _EVENT_TRIGGER) if "trigger" in data else None,
    )


def parse_hardware(data: JsonObject) -> Hardware:
    """Build a ``Hardware`` from a document that passed its schema."""
    return Hardware(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]) if "name" in data else None,
        boards=tuple(parse_hardware_board(as_object(item)) for item in as_list(data["boards"])),
        elements=tuple(parse_element(as_object(item)) for item in as_list(data["elements"])),
    )


def parse_hardware_board(data: JsonObject) -> HardwareBoard:
    """Build a ``HardwareBoard`` from a document that passed its schema."""
    return HardwareBoard(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        model=as_str(data["model"]),
    )


def parse_element(data: JsonObject) -> Element:
    """Build a ``Element`` from a document that passed its schema."""
    return Element(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        board=as_uuid(data["board"]),
        type=as_choice(data["type"], _ELEMENT_TYPE),
        pin=as_int(data["pin"]) if "pin" in data else None,
        active_low=as_bool(data["activeLow"]) if "activeLow" in data else False,
        bus=as_str(data["bus"]) if "bus" in data else None,
        address=as_int(data["address"]) if "address" in data else None,
        config=tuple(parse_named_value(as_object(item)) for item in as_list(data["config"])) if "config" in data else (),
    )


def parse_package(data: JsonObject) -> Package:
    """Build a ``Package`` from a document that passed its schema."""
    return Package(
        hash=as_str(data["hash"]),
        project=parse_package_project(as_object(data["project"])),
        board=parse_package_board(as_object(data["board"])),
        elements=tuple(parse_package_element(as_object(item)) for item in as_list(data["elements"])),
        variables=tuple(parse_package_variable(as_object(item)) for item in as_list(data["variables"])),
        sequences=tuple(parse_package_sequence(as_object(item)) for item in as_list(data["sequences"])),
        events=tuple(parse_package_event(as_object(item)) for item in as_list(data["events"])),
        schedules=tuple(parse_package_schedule(as_object(item)) for item in as_list(data["schedules"])),
        automations=tuple(parse_package_automation(as_object(item)) for item in as_list(data["automations"])),
    )


def parse_package_project(data: JsonObject) -> PackageProject:
    """Build a ``PackageProject`` from a document that passed its schema."""
    return PackageProject(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
    )


def parse_package_board(data: JsonObject) -> PackageBoard:
    """Build a ``PackageBoard`` from a document that passed its schema."""
    return PackageBoard(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        model=as_str(data["model"]),
    )


def parse_package_element(data: JsonObject) -> PackageElement:
    """Build a ``PackageElement`` from a document that passed its schema."""
    return PackageElement(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        type=as_str(data["type"]),
        pin=as_int(data["pin"]) if "pin" in data else None,
        active_low=as_bool(data["activeLow"]) if "activeLow" in data else False,
        bus=as_str(data["bus"]) if "bus" in data else None,
        address=as_int(data["address"]) if "address" in data else None,
        config=tuple(parse_named_value(as_object(item)) for item in as_list(data["config"])),
    )


def parse_package_variable(data: JsonObject) -> PackageVariable:
    """Build a ``PackageVariable`` from a document that passed its schema."""
    return PackageVariable(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        type=as_choice(data["type"], _PACKAGE_VARIABLE_TYPE),
        initial=as_scalar(data["initial"]),
        min=as_float(data["min"]) if "min" in data else None,
        max=as_float(data["max"]) if "max" in data else None,
        persistent=as_bool(data["persistent"]),
        setting=as_bool(data["setting"]),
    )


def parse_package_sequence(data: JsonObject) -> PackageSequence:
    """Build a ``PackageSequence`` from a document that passed its schema."""
    return PackageSequence(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        priority=as_int(data["priority"]),
        exclusive_group=as_str(data["exclusiveGroup"]) if "exclusiveGroup" in data else None,
        when_done=as_choice(data["whenDone"], _PACKAGE_SEQUENCE_WHEN_DONE),
        when_started_again=as_choice(data["whenStartedAgain"], _PACKAGE_SEQUENCE_WHEN_STARTED_AGAIN),
        duration_ms=as_int(data["durationMs"]),
        commands=tuple(parse_command(as_object(item)) for item in as_list(data["commands"])),
    )


def parse_command(data: JsonObject) -> Command:
    """Build a ``Command`` from a document that passed its schema."""
    return Command(
        clip=as_uuid(data["clip"]),
        element=as_uuid(data["element"]),
        at_ms=as_int(data["atMs"]),
        duration_ms=as_int(data["durationMs"]),
        until_ms=as_int(data["untilMs"]) if "untilMs" in data else None,
        action=as_str(data["action"]),
        arguments=tuple(parse_command_argument(as_object(item)) for item in as_list(data["arguments"])),
    )


def parse_command_argument(data: JsonObject) -> CommandArgument:
    """Build a ``CommandArgument`` from a document that passed its schema."""
    return CommandArgument(
        name=as_str(data["name"]),
        value=as_scalar(data["value"]) if "value" in data else None,
        variable=as_uuid(data["variable"]) if "variable" in data else None,
    )


def parse_package_event(data: JsonObject) -> PackageEvent:
    """Build a ``PackageEvent`` from a document that passed its schema."""
    return PackageEvent(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        source=as_choice(data["source"], _PACKAGE_EVENT_SOURCE),
        element=as_uuid(data["element"]) if "element" in data else None,
        trigger=as_choice(data["trigger"], _PACKAGE_EVENT_TRIGGER) if "trigger" in data else None,
    )


def parse_package_schedule(data: JsonObject) -> PackageSchedule:
    """Build a ``PackageSchedule`` from a document that passed its schema."""
    return PackageSchedule(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        times=tuple(parse_package_time(as_object(item)) for item in as_list(data["times"])),
        windows=tuple(parse_package_window(as_object(item)) for item in as_list(data["windows"])),
    )


def parse_package_time(data: JsonObject) -> PackageTime:
    """Build a ``PackageTime`` from a document that passed its schema."""
    return PackageTime(
        days=tuple(as_choice(item, _PACKAGE_TIME_DAYS) for item in as_list(data["days"])),
        at=as_str(data["at"]),
    )


def parse_package_window(data: JsonObject) -> PackageWindow:
    """Build a ``PackageWindow`` from a document that passed its schema."""
    return PackageWindow(
        days=tuple(as_choice(item, _PACKAGE_WINDOW_DAYS) for item in as_list(data["days"])),
        from_=as_str(data["from"]),
        to=as_str(data["to"]),
    )


def parse_package_automation(data: JsonObject) -> PackageAutomation:
    """Build a ``PackageAutomation`` from a document that passed its schema."""
    return PackageAutomation(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        enabled=as_bool(data["enabled"]),
        when=tuple(as_uuid(item) for item in as_list(data["when"])),
        if_=as_str(data["if"]) if "if" in data else None,
        do=tuple(parse_package_action(as_object(item)) for item in as_list(data["do"])),
    )


def parse_package_action(data: JsonObject) -> PackageAction:
    """Build a ``PackageAction`` from a document that passed its schema."""
    return PackageAction(
        action=as_choice(data["action"], _PACKAGE_ACTION_ACTION),
        sequence=as_uuid(data["sequence"]) if "sequence" in data else None,
        variable=as_uuid(data["variable"]) if "variable" in data else None,
        value=as_scalar(data["value"]) if "value" in data else None,
    )


def parse_project(data: JsonObject) -> Project:
    """Build a ``Project`` from a document that passed its schema."""
    return Project(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        description=as_str(data["description"]) if "description" in data else None,
    )


def parse_schedule(data: JsonObject) -> Schedule:
    """Build a ``Schedule`` from a document that passed its schema."""
    return Schedule(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        times=tuple(parse_schedule_time(as_object(item)) for item in as_list(data["times"])) if "times" in data else (),
        windows=tuple(parse_schedule_window(as_object(item)) for item in as_list(data["windows"])) if "windows" in data else (),
    )


def parse_schedule_time(data: JsonObject) -> ScheduleTime:
    """Build a ``ScheduleTime`` from a document that passed its schema."""
    return ScheduleTime(
        days=tuple(as_choice(item, _SCHEDULE_TIME_DAYS) for item in as_list(data["days"])),
        at=as_str(data["at"]),
    )


def parse_schedule_window(data: JsonObject) -> ScheduleWindow:
    """Build a ``ScheduleWindow`` from a document that passed its schema."""
    return ScheduleWindow(
        days=tuple(as_choice(item, _SCHEDULE_WINDOW_DAYS) for item in as_list(data["days"])),
        from_=as_str(data["from"]),
        to=as_str(data["to"]),
    )


def parse_sequence(data: JsonObject) -> Sequence:
    """Build a ``Sequence`` from a document that passed its schema."""
    return Sequence(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        description=as_str(data["description"]) if "description" in data else None,
        priority=as_int(data["priority"]) if "priority" in data else 0,
        exclusive_group=as_str(data["exclusiveGroup"]) if "exclusiveGroup" in data else None,
        when_done=as_choice(data["whenDone"], _SEQUENCE_WHEN_DONE) if "whenDone" in data else "end",
        when_started_again=as_choice(data["whenStartedAgain"], _SEQUENCE_WHEN_STARTED_AGAIN) if "whenStartedAgain" in data else "restart",
        parameters=tuple(parse_parameter(as_object(item)) for item in as_list(data["parameters"])) if "parameters" in data else (),
        tracks=tuple(parse_track(as_object(item)) for item in as_list(data["tracks"])),
        blocks=tuple(parse_block(as_object(item)) for item in as_list(data["blocks"])) if "blocks" in data else (),
    )


def parse_parameter(data: JsonObject) -> Parameter:
    """Build a ``Parameter`` from a document that passed its schema."""
    return Parameter(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        type=as_choice(data["type"], _PARAMETER_TYPE),
    )


def parse_track(data: JsonObject) -> Track:
    """Build a ``Track`` from a document that passed its schema."""
    return Track(
        element=as_uuid(data["element"]),
        clips=tuple(parse_clip(as_object(item)) for item in as_list(data["clips"])),
    )


def parse_clip(data: JsonObject) -> Clip:
    """Build a ``Clip`` from a document that passed its schema."""
    return Clip(
        id=as_uuid(data["id"]),
        at_ms=as_int(data["atMs"]),
        duration_ms=as_int(data["durationMs"]),
        action=as_str(data["action"]),
        arguments=tuple(parse_clip_argument(as_object(item)) for item in as_list(data["arguments"])) if "arguments" in data else (),
    )


def parse_clip_argument(data: JsonObject) -> ClipArgument:
    """Build a ``ClipArgument`` from a document that passed its schema."""
    return ClipArgument(
        name=as_str(data["name"]),
        value=as_scalar(data["value"]) if "value" in data else None,
        value_of=as_str(data["valueOf"]) if "valueOf" in data else None,
    )


def parse_block(data: JsonObject) -> Block:
    """Build a ``Block`` from a document that passed its schema."""
    return Block(
        id=as_uuid(data["id"]),
        sequence=as_uuid(data["sequence"]),
        at_ms=as_int(data["atMs"]),
        arguments=tuple(parse_argument(as_object(item)) for item in as_list(data["arguments"])) if "arguments" in data else (),
    )


def parse_argument(data: JsonObject) -> Argument:
    """Build a ``Argument`` from a document that passed its schema."""
    return Argument(
        parameter=as_uuid(data["parameter"]),
        element=as_uuid(data["element"]) if "element" in data else None,
        value=as_scalar(data["value"]) if "value" in data else None,
        value_of=as_str(data["valueOf"]) if "valueOf" in data else None,
    )


def parse_variables(data: JsonObject) -> Variables:
    """Build a ``Variables`` from a document that passed its schema."""
    return Variables(
        id=as_uuid(data["id"]),
        constants=tuple(parse_constant(as_object(item)) for item in as_list(data["constants"])),
        variables=tuple(parse_variable(as_object(item)) for item in as_list(data["variables"])),
        exports=tuple(as_str(item) for item in as_list(data["exports"])) if "exports" in data else (),
        imports=tuple(parse_variable_import(as_object(item)) for item in as_list(data["imports"])) if "imports" in data else (),
    )


def parse_constant(data: JsonObject) -> Constant:
    """Build a ``Constant`` from a document that passed its schema."""
    return Constant(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        type=as_choice(data["type"], _CONSTANT_TYPE),
        value=as_scalar(data["value"]),
    )


def parse_variable(data: JsonObject) -> Variable:
    """Build a ``Variable`` from a document that passed its schema."""
    return Variable(
        id=as_uuid(data["id"]),
        name=as_str(data["name"]),
        type=as_choice(data["type"], _VARIABLE_TYPE),
        initial=as_scalar(data["initial"]),
        min=as_float(data["min"]) if "min" in data else None,
        max=as_float(data["max"]) if "max" in data else None,
        persistent=as_bool(data["persistent"]) if "persistent" in data else False,
        setting=as_bool(data["setting"]) if "setting" in data else False,
    )


def parse_variable_import(data: JsonObject) -> VariableImport:
    """Build a ``VariableImport`` from a document that passed its schema."""
    return VariableImport(
        from_=as_uuid(data["from"]),
        name=as_str(data["name"]),
    )
