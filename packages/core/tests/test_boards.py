"""Board profiles: the shipped ones are valid, and broken ones are reported with their place."""

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

import pytest

from primum_core.boards import gpio_lines
from primum_core.errors import CoreErrorCode
from primum_core.formats import read_board_profile
from primum_core.generated.model import BoardProfile

BOARDS = Path(__file__).resolve().parents[3] / "boards"
RPI4B = BOARDS / "rpi4b.json"


def _rpi4b() -> BoardProfile:
    parsed = read_board_profile(PurePosixPath("rpi4b.json"), RPI4B.read_bytes())
    assert parsed.value is not None, parsed.issues
    return parsed.value


def _issues(change: dict[str, object]) -> list[tuple[CoreErrorCode, dict[str, object], str]]:
    document = json.loads(RPI4B.read_text(encoding="utf-8"))
    document.update(change)
    parsed = read_board_profile(PurePosixPath("rpi4b.json"), json.dumps(document).encode())
    assert parsed.value is None
    return [
        (issue.code, dict(issue.params), issue.location.pointer if issue.location else "")
        for issue in parsed.issues
    ]


def _pins(*pins: Mapping[str, object]) -> dict[str, object]:
    """A tiny header: no buses, channels or reserved pins to refer to it."""
    return {"pins": list(pins), "buses": [], "pwmChannels": [], "reserved": []}


GPIO_17: dict[str, object] = {
    "physical": 11,
    "kind": "gpio",
    "gpio": 17,
    "line": 17,
    "defaultPull": "down",
}


@pytest.mark.parametrize("path", sorted(BOARDS.glob("*.json")), ids=lambda path: path.stem)
def test_every_shipped_profile_is_valid_and_named_after_its_model(path: Path) -> None:
    parsed = read_board_profile(PurePosixPath(path.name), path.read_bytes())

    assert parsed.issues == ()
    assert parsed.value is not None
    assert parsed.value.model == path.stem


def test_the_raspberry_pi_4_header_has_40_pins_and_28_gpios_on_lines_of_the_same_number() -> None:
    profile = _rpi4b()

    assert [pin.physical for pin in profile.pins] == list(range(1, 41))
    assert gpio_lines(profile) == {gpio: gpio for gpio in range(28)}
    assert profile.gpio_chip.label == "pinctrl-bcm2711"


def test_the_raspberry_pi_4_profile_knows_its_buses_pwm_and_reserved_pins() -> None:
    profile = _rpi4b()

    i2c1 = next(bus for bus in profile.buses if bus.id == "i2c1")
    assert {signal.name: signal.gpio for signal in i2c1.signals} == {"sda": 2, "scl": 3}
    assert {channel.id: channel.gpios for channel in profile.pwm_channels} == {
        "pwm0": (12, 18),
        "pwm1": (13, 19),
    }
    assert {reserved.gpio for reserved in profile.reserved} == {0, 1}


def test_gpio_17_is_physical_pin_11_and_pulled_down_at_power_on() -> None:
    pin = next(pin for pin in _rpi4b().pins if pin.gpio == 17)

    assert (pin.physical, pin.default_pull) == (11, "down")


@pytest.mark.parametrize(
    ("pins", "expected"),
    [
        (
            [GPIO_17, {**GPIO_17, "gpio": 18, "line": 18}],
            (CoreErrorCode.BOARD_DUPLICATE_PIN, {"physical": 11}, "/pins/1"),
        ),
        (
            [GPIO_17, {**GPIO_17, "physical": 12, "line": 18}],
            (CoreErrorCode.BOARD_DUPLICATE_GPIO, {"gpio": 17}, "/pins/1"),
        ),
        (
            [GPIO_17, {**GPIO_17, "physical": 12, "gpio": 18}],
            (CoreErrorCode.BOARD_DUPLICATE_LINE, {"line": 17}, "/pins/1"),
        ),
        (
            [{"physical": 1, "kind": "ground", "gpio": 4}],
            (CoreErrorCode.BOARD_POWER_PIN_WITH_GPIO, {"physical": 1}, "/pins/0"),
        ),
        (
            [{"physical": 11, "kind": "gpio", "gpio": 17}],
            (CoreErrorCode.BOARD_INCOMPLETE_GPIO_PIN, {"physical": 11}, "/pins/0"),
        ),
    ],
)
def test_pin_problems_are_reported_at_the_pin(
    pins: list[dict[str, object]], expected: tuple[CoreErrorCode, dict[str, object], str]
) -> None:
    assert _issues(_pins(*pins)) == [expected]


def test_buses_channels_and_reserved_pins_must_name_gpios_the_board_has() -> None:
    change = {
        **_pins(GPIO_17),
        "buses": [{"id": "i2c1", "kind": "i2c", "signals": [{"name": "sda", "gpio": 2}]}],
        "pwmChannels": [{"id": "pwm0", "channel": 0, "gpios": [17, 18]}],
        "reserved": [{"gpio": 0, "reason": "hat_eeprom"}],
    }

    assert _issues(change) == [
        (CoreErrorCode.BOARD_UNKNOWN_GPIO, {"gpio": 2}, "/buses/0/signals/0/gpio"),
        (CoreErrorCode.BOARD_UNKNOWN_GPIO, {"gpio": 18}, "/pwmChannels/0/gpios/1"),
        (CoreErrorCode.BOARD_UNKNOWN_GPIO, {"gpio": 0}, "/reserved/0/gpio"),
    ]


def test_bus_and_channel_names_are_unique() -> None:
    change = {
        **_pins(GPIO_17),
        "pwmChannels": [
            {"id": "pwm0", "channel": 0, "gpios": [17]},
            {"id": "pwm0", "channel": 1, "gpios": [17]},
        ],
    }

    assert _issues(change) == [
        (CoreErrorCode.BOARD_DUPLICATE_ID, {"id": "pwm0"}, "/pwmChannels/1/id")
    ]


def test_an_incomplete_gpio_pin_is_reported_once_not_again_by_each_reference() -> None:
    change = {
        **_pins({"physical": 11, "kind": "gpio", "gpio": 17}),
        "pwmChannels": [{"id": "pwm0", "channel": 0, "gpios": [17]}],
    }

    assert _issues(change) == [
        (CoreErrorCode.BOARD_INCOMPLETE_GPIO_PIN, {"physical": 11}, "/pins/0")
    ]
