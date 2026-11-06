"""Resources of a board given out to its elements: GPIOs, PWM channels, I2C addresses."""

from primum_core.errors import CoreErrorCode
from project_builder import Ids, Project

PI = 3
HW = "hardware.hw"


def _element(
    ids: Ids, number: int, name: str, type_: str = "digital_output", **fields: object
) -> dict[str, object]:
    return {"id": ids(number), "name": name, "board": ids(PI), "type": type_, **fields}


def _hardware(
    project: Project, ids: Ids, *elements: dict[str, object], model: str = "rpi4b"
) -> Project:
    """Replaces the fixture's hardware with ``elements`` on one board."""
    return project.add(
        HW,
        "hardware",
        ids(2),
        boards=[{"id": ids(PI), "name": "Pi", "model": model}],
        elements=list(elements),
    )


def test_distinct_free_gpios_pass(project: Project, ids: Ids) -> None:
    _hardware(
        project,
        ids,
        _element(ids, 4, "LED", pin=17),
        _element(ids, 5, "Button", "digital_input", pin=27),
        _element(ids, 6, "Fan", "pwm_output", pin=18),
        _element(ids, 7, "Expander", "i2c_device", bus="i2c1", address=32),
    )

    assert project.found() == []


def test_a_board_of_an_unknown_model_is_reported_and_its_elements_skipped(
    project: Project, ids: Ids
) -> None:
    _hardware(project, ids, _element(ids, 4, "LED", pin=99), model="rpi9")

    assert project.found() == [
        (
            CoreErrorCode.BOARD_UNKNOWN_MODEL,
            {"model": "rpi9", "board": "Pi"},
            HW,
            "/boards/0/model",
        )
    ]


def test_a_gpio_the_board_does_not_have(project: Project, ids: Ids) -> None:
    _hardware(project, ids, _element(ids, 4, "LED", pin=28))

    assert project.found() == [
        (CoreErrorCode.PIN_NOT_ON_BOARD, {"pin": 28, "board": "Pi"}, HW, "/elements/0/pin")
    ]


def test_a_reserved_gpio(project: Project, ids: Ids) -> None:
    _hardware(project, ids, _element(ids, 4, "LED", pin=0))

    assert project.found() == [
        (CoreErrorCode.PIN_RESERVED, {"pin": 0, "physical": 27}, HW, "/elements/0/pin")
    ]


def test_two_elements_on_one_gpio_name_each_other(project: Project, ids: Ids) -> None:
    _hardware(project, ids, _element(ids, 4, "LED", pin=17), _element(ids, 5, "Relay", pin=17))

    assert project.found() == [
        (
            CoreErrorCode.PIN_IN_USE,
            {"pin": 17, "physical": 11, "other": "LED"},
            HW,
            "/elements/1/pin",
        )
    ]


def test_a_bus_with_a_device_claims_its_gpios(project: Project, ids: Ids) -> None:
    _hardware(
        project,
        ids,
        _element(ids, 4, "LED", pin=2),
        _element(ids, 7, "Expander", "i2c_device", bus="i2c1", address=32),
    )

    assert project.found() == [
        (
            CoreErrorCode.PIN_CLAIMED_BY_BUS,
            {"pin": 2, "physical": 3, "bus": "i2c1"},
            HW,
            "/elements/0/pin",
        )
    ]


def test_gpio_2_is_free_while_no_device_uses_the_bus(project: Project, ids: Ids) -> None:
    _hardware(project, ids, _element(ids, 4, "LED", pin=2))

    assert project.found() == []


def test_a_pwm_output_needs_a_pin_with_hardware_pwm(project: Project, ids: Ids) -> None:
    _hardware(project, ids, _element(ids, 6, "Fan", "pwm_output", pin=17))

    assert project.found() == [
        (
            CoreErrorCode.PIN_FUNCTION_UNAVAILABLE,
            {"pin": 17, "physical": 11},
            HW,
            "/elements/0/pin",
        )
    ]


def test_two_pwm_outputs_cannot_share_a_channel(project: Project, ids: Ids) -> None:
    _hardware(
        project,
        ids,
        _element(ids, 6, "Fan", "pwm_output", pin=12),
        _element(ids, 8, "Dimmer", "pwm_output", pin=18),
    )

    assert project.found() == [
        (
            CoreErrorCode.PWM_CHANNEL_IN_USE,
            {"pin": 18, "physical": 12, "other": "Fan"},
            HW,
            "/elements/1/pin",
        )
    ]


def test_a_device_on_a_bus_the_board_does_not_have(project: Project, ids: Ids) -> None:
    _hardware(project, ids, _element(ids, 7, "Expander", "i2c_device", bus="i2c7", address=32))

    assert project.found() == [
        (CoreErrorCode.BUS_NOT_ON_BOARD, {"bus": "i2c7", "board": "Pi"}, HW, "/elements/0/bus")
    ]


def test_a_device_on_a_bus_of_another_kind(project: Project, ids: Ids) -> None:
    _hardware(project, ids, _element(ids, 7, "Expander", "i2c_device", bus="spi0", address=32))

    assert project.found() == [
        (CoreErrorCode.BUS_NOT_I2C, {"bus": "spi0", "board": "Pi"}, HW, "/elements/0/bus")
    ]


def test_two_devices_at_one_address_on_one_bus(project: Project, ids: Ids) -> None:
    _hardware(
        project,
        ids,
        _element(ids, 7, "Expander", "i2c_device", bus="i2c1", address=32),
        _element(ids, 8, "Sensor", "i2c_device", bus="i2c1", address=32),
    )

    assert project.found() == [
        (
            CoreErrorCode.I2C_ADDRESS_IN_USE,
            {"address": 32, "bus": "i2c1", "other": "Expander"},
            HW,
            "/elements/1/address",
        )
    ]


def test_boards_are_independent(project: Project, ids: Ids) -> None:
    project.add(
        HW,
        "hardware",
        ids(2),
        boards=[
            {"id": ids(PI), "name": "Pi", "model": "rpi4b"},
            {"id": ids(9), "name": "Other Pi", "model": "rpi4b"},
        ],
        elements=[
            _element(ids, 4, "LED", pin=17),
            {**_element(ids, 5, "Relay", pin=17), "board": ids(9)},
        ],
    )

    assert project.found() == []
