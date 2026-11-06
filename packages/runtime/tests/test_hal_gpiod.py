"""GpiodHal without a Pi: `gpiod.Chip` is replaced by a fake that records the calls.

The real kernel interaction is covered by the `hw` test on the Pi; these tests cover our side:
the checks before a line is requested, the requested configuration, the values written, the
release and the error mapping.
"""

import errno
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from primum_runtime.errors import PrimumError
from primum_runtime.hal import BoardGpio, OutputSpec, create_hal

gpiod = pytest.importorskip("gpiod", reason="gpiod is only installed on Linux")
from gpiod import ChipInfo, LineSettings  # noqa: E402 (after the importorskip above)
from gpiod.line import Direction, Value  # noqa: E402

from primum_runtime.hal import gpiod_hal  # noqa: E402 (needs gpiod)
from primum_runtime.hal.gpiod_hal import GpiodHal  # noqa: E402

CHIP = "/dev/gpiochip7"
LABEL = "pinctrl-test"
NUM_LINES = 58  # as the GPIO chip of a Raspberry Pi 4
# GPIO 5 sits on line 40 to show the HAL uses the profile's line, not the GPIO number; GPIO 6
# names a line the chip does not have (a profile that disagrees with the chip).
BOARD = BoardGpio(model="test", chip_label=LABEL, lines={2: 2, 5: 40, 6: NUM_LINES, 17: 17})


@dataclass
class FakeRequest:
    """Stands in for `gpiod.LineRequest`: records what the HAL asks of the line."""

    consumer: str | None
    config: dict[int, LineSettings]
    writes: list[tuple[int, Value]] = field(default_factory=list[tuple[int, Value]])
    released: bool = False

    def set_value(self, line: int, value: Value) -> None:
        self.writes.append((line, value))

    def get_value(self, line: int) -> Value:
        values = [value for written_line, value in self.writes if written_line == line]
        return values[-1] if values else Value.INACTIVE

    def release(self) -> None:
        self.released = True


@dataclass(frozen=True)
class FakeLineInfo:
    """The fields of `gpiod.LineInfo` the HAL reads."""

    used: bool
    consumer: str | None


@dataclass
class FakeChip:
    """Stands in for `gpiod.Chip`: lines in `owners` are used, by the consumer named there.

    Lines held by kernel drivers report ``None`` as consumer, as the real API does (verified on
    a Pi 4 with gpiod 2.2.0).
    """

    path: str
    label: str = LABEL
    owners: dict[int, str | None] = field(default_factory=dict[int, str | None])
    request_error: Exception | None = None
    info_error: Exception | None = None
    requests: list[FakeRequest] = field(default_factory=list[FakeRequest])
    closed: bool = False

    def get_info(self) -> ChipInfo:
        if self.info_error is not None:
            raise self.info_error
        return ChipInfo(name=self.path.removeprefix("/dev/"), label=self.label, num_lines=NUM_LINES)

    def get_line_info(self, line: int) -> FakeLineInfo:
        return FakeLineInfo(line in self.owners, self.owners.get(line))

    def request_lines(
        self, config: dict[int, LineSettings], consumer: str | None = None
    ) -> FakeRequest:
        if self.request_error is not None:
            raise self.request_error
        request = FakeRequest(consumer, config)
        self.requests.append(request)
        return request

    def close(self) -> None:
        self.closed = True


def _install(monkeypatch: pytest.MonkeyPatch, *chips: FakeChip) -> None:
    """Make these the GPIO chips of the system, in this order."""
    by_path = {chip.path: chip for chip in chips}
    monkeypatch.setattr(gpiod_hal, "_chip_paths", lambda: list(by_path))
    monkeypatch.setattr(gpiod, "Chip", by_path.__getitem__)


@pytest.fixture
def other_chip() -> FakeChip:
    """Another chip found first, as the GPIO expander of a Pi 4 may be."""
    return FakeChip("/dev/gpiochip0", label="raspberrypi-exp-gpio")


@pytest.fixture
def chip(monkeypatch: pytest.MonkeyPatch, other_chip: FakeChip) -> FakeChip:
    fake = FakeChip(CHIP)
    _install(monkeypatch, other_chip, fake)
    return fake


def test_output_requests_one_inactive_output_line(chip: FakeChip) -> None:
    with GpiodHal(BOARD) as hal:
        hal.digital_output(OutputSpec(pin=17, active_low=True))

        (request,) = chip.requests
        settings = request.config[17]
        assert request.consumer == "primum"
        assert settings.direction == Direction.OUTPUT
        assert settings.output_value == Value.INACTIVE
        assert settings.active_low


def test_set_writes_active_and_inactive_values(chip: FakeChip) -> None:
    with GpiodHal(BOARD) as hal:
        output = hal.digital_output(OutputSpec(pin=17))

        output.set(True)
        assert output.read()
        output.set(False)

        assert chip.requests[0].writes == [(17, Value.ACTIVE), (17, Value.INACTIVE)]


def test_close_writes_the_safe_state_releases_the_line_and_closes_the_chip(
    chip: FakeChip,
) -> None:
    hal = GpiodHal(BOARD)
    hal.digital_output(OutputSpec(pin=17)).set(True)

    hal.close()

    assert chip.requests[0].writes[-1] == (17, Value.INACTIVE)
    assert chip.requests[0].released
    assert chip.closed


def test_a_profile_line_the_chip_does_not_have_raises_profile_mismatch(chip: FakeChip) -> None:
    with GpiodHal(BOARD) as hal, pytest.raises(PrimumError) as raised:
        hal.digital_output(OutputSpec(pin=6))

    assert raised.value.code == "hal.profile_mismatch"
    assert raised.value.params == {"pin": 6, "line": NUM_LINES, "chip": CHIP, "lines": NUM_LINES}
    assert chip.requests == []


def test_line_held_by_a_kernel_driver_raises_pin_unavailable_without_consumer(
    chip: FakeChip,
) -> None:
    # GPIO 2 is I2C SDA on a Pi 4 with I2C on: gpioinfo prints "kernel", the API returns None.
    chip.owners[2] = None

    with GpiodHal(BOARD) as hal, pytest.raises(PrimumError) as raised:
        hal.digital_output(OutputSpec(pin=2))

    assert raised.value.code == "hal.pin_unavailable"
    assert raised.value.params == {"pin": 2, "chip": CHIP}
    assert chip.requests == []


def test_line_held_by_a_named_consumer_raises_pin_unavailable_with_it(chip: FakeChip) -> None:
    chip.owners[17] = "other-app"

    with GpiodHal(BOARD) as hal, pytest.raises(PrimumError) as raised:
        hal.digital_output(OutputSpec(pin=17))

    assert raised.value.params == {"pin": 17, "chip": CHIP, "consumer": "other-app"}
    assert chip.requests == []


def test_einval_from_the_request_raises_pin_unavailable(chip: FakeChip) -> None:
    # What gpiod raises on a Pi 4 for GPIO 2 owned by the kernel, if the check missed it.
    chip.request_error = ValueError(errno.EINVAL, "Invalid argument")

    with GpiodHal(BOARD) as hal, pytest.raises(PrimumError) as raised:
        hal.digital_output(OutputSpec(pin=2))

    assert raised.value.code == "hal.pin_unavailable"
    assert raised.value.params["pin"] == 2
    assert isinstance(raised.value.__cause__, ValueError)


def test_busy_line_raises_pin_unavailable_with_the_system_text(chip: FakeChip) -> None:
    chip.request_error = OSError(errno.EBUSY, "Device or resource busy")

    with GpiodHal(BOARD) as hal, pytest.raises(PrimumError) as raised:
        hal.digital_output(OutputSpec(pin=17))

    assert raised.value.code == "hal.pin_unavailable"
    assert raised.value.params == {"pin": 17, "chip": CHIP, "detail": "Device or resource busy"}
    assert isinstance(raised.value.__cause__, OSError)


def test_the_chip_is_found_by_its_label_and_the_others_are_closed(
    chip: FakeChip, other_chip: FakeChip
) -> None:
    with GpiodHal(BOARD) as hal:
        hal.digital_output(OutputSpec(pin=17))

    assert other_chip.closed
    assert chip.requests


def test_each_gpio_is_requested_on_the_line_the_profile_gives_it(chip: FakeChip) -> None:
    with GpiodHal(BOARD) as hal:
        hal.digital_output(OutputSpec(pin=5)).set(True)

    assert list(chip.requests[0].config) == [40]
    assert chip.requests[0].writes[0] == (40, Value.ACTIVE)


def test_a_gpio_the_board_does_not_have_raises_pin_invalid_before_any_request(
    chip: FakeChip,
) -> None:
    with GpiodHal(BOARD) as hal, pytest.raises(PrimumError) as raised:
        hal.digital_output(OutputSpec(pin=27))

    assert raised.value.code == "hal.pin_invalid"
    assert raised.value.params == {"pin": 27, "board": "test"}
    assert chip.requests == []


def test_no_chip_with_the_label_raises_chip_not_found_naming_the_chips_found(
    monkeypatch: pytest.MonkeyPatch, other_chip: FakeChip
) -> None:
    _install(monkeypatch, other_chip)

    with pytest.raises(PrimumError) as raised:
        GpiodHal(BOARD)

    assert raised.value.code == "hal.chip_not_found"
    assert raised.value.params == {
        "chip": LABEL,
        "detail": "found /dev/gpiochip0 (raspberrypi-exp-gpio)",
    }
    assert other_chip.closed


def test_no_chip_at_all_raises_chip_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)

    with pytest.raises(PrimumError) as raised:
        GpiodHal(BOARD)

    assert raised.value.code == "hal.chip_not_found"
    assert raised.value.params == {"chip": LABEL, "detail": "no GPIO chip found"}


def test_a_chip_that_fails_is_skipped_and_the_search_goes_on(
    monkeypatch: pytest.MonkeyPatch, other_chip: FakeChip
) -> None:
    other_chip.info_error = OSError(errno.EIO, "Input/output error")
    chip = FakeChip(CHIP)
    _install(monkeypatch, other_chip, chip)

    with GpiodHal(BOARD) as hal:
        hal.digital_output(OutputSpec(pin=17))

    assert other_chip.closed
    assert chip.requests


def test_a_chip_that_fails_is_named_if_no_chip_has_the_label(chip: FakeChip) -> None:
    chip.info_error = OSError(errno.EIO, "Input/output error")

    with pytest.raises(PrimumError) as raised:
        GpiodHal(BOARD)

    assert raised.value.code == "hal.chip_not_found"
    assert raised.value.params == {
        "chip": LABEL,
        "detail": f"found /dev/gpiochip0 (raspberrypi-exp-gpio), {CHIP}: Input/output error",
    }
    assert chip.closed


def test_a_chip_without_permission_is_skipped_if_another_has_the_label(
    monkeypatch: pytest.MonkeyPatch, chip: FakeChip
) -> None:
    def open_chip(path: str) -> FakeChip:
        if path != CHIP:
            raise PermissionError(errno.EACCES, "Permission denied")
        return chip

    monkeypatch.setattr(gpiod_hal, "_chip_paths", lambda: ["/dev/gpiochip0", CHIP])
    monkeypatch.setattr(gpiod, "Chip", open_chip)

    with GpiodHal(BOARD) as hal:
        hal.digital_output(OutputSpec(pin=17))

    assert chip.requests


def test_no_permission_and_no_label_raises_chip_access_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied(_path: str) -> FakeChip:
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(gpiod_hal, "_chip_paths", lambda: [CHIP])
    monkeypatch.setattr(gpiod, "Chip", denied)

    with pytest.raises(PrimumError) as raised:
        GpiodHal(BOARD)

    assert raised.value.code == "hal.chip_access_denied"
    assert raised.value.params == {"chip": LABEL, "detail": f"found {CHIP}: Permission denied"}


def test_create_hal_returns_the_gpio_hal_for_the_board(chip: FakeChip) -> None:
    with create_hal(simulate=False, board=BOARD) as hal:
        assert isinstance(hal, GpiodHal)
        hal.digital_output(OutputSpec(pin=17))

    assert chip.requests


def test_links_to_a_chip_are_not_opened_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "gpiochip0").touch()
    (tmp_path / "gpiochip1").touch()
    (tmp_path / "gpiochip4").symlink_to(tmp_path / "gpiochip0")
    monkeypatch.setattr(gpiod_hal, "DEVICES", tmp_path)

    assert gpiod_hal._chip_paths() == [str(tmp_path / "gpiochip0"), str(tmp_path / "gpiochip1")]  # pyright: ignore[reportPrivateUsage] -- what the HAL opens
