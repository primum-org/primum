"""GpiodHal without a Pi: `gpiod.Chip` is replaced by a fake that records the calls.

The real kernel interaction is covered by the `hw` test on the Pi; these tests cover our side:
the checks before a line is requested, the requested configuration, the values written, the
release and the error mapping.
"""

import errno
from dataclasses import dataclass, field

import pytest

from primum_runtime.errors import PrimumError
from primum_runtime.hal import OutputSpec, create_hal

gpiod = pytest.importorskip("gpiod", reason="gpiod is only installed on Linux")
from gpiod import ChipInfo, LineSettings  # noqa: E402 (after the importorskip above)
from gpiod.line import Direction, Value  # noqa: E402

from primum_runtime.hal.gpiod_hal import GpiodHal  # noqa: E402 (needs gpiod)

CHIP = "/dev/gpiochip7"
NUM_LINES = 58  # as /dev/gpiochip0 on a Raspberry Pi 4


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
    """The two fields of `gpiod.LineInfo` the HAL reads."""

    used: bool
    consumer: str


@dataclass
class FakeChip:
    """Stands in for `gpiod.Chip`: lines in `owners` are used by another consumer."""

    path: str
    owners: dict[int, str] = field(default_factory=dict[int, str])
    request_error: Exception | None = None
    requests: list[FakeRequest] = field(default_factory=list[FakeRequest])
    closed: bool = False

    def get_info(self) -> ChipInfo:
        return ChipInfo(name="gpiochip7", label="fake", num_lines=NUM_LINES)

    def get_line_info(self, line: int) -> "FakeLineInfo":
        consumer = self.owners.get(line)
        return FakeLineInfo(used=consumer is not None, consumer=consumer or "")

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


@pytest.fixture
def chip(monkeypatch: pytest.MonkeyPatch) -> FakeChip:
    fake = FakeChip(CHIP)

    def open_chip(path: str) -> FakeChip:
        if path != CHIP:
            raise FileNotFoundError(errno.ENOENT, "No such file or directory")
        return fake

    monkeypatch.setattr(gpiod, "Chip", open_chip)
    return fake


def test_output_requests_one_inactive_output_line(chip: FakeChip) -> None:
    with GpiodHal(CHIP) as hal:
        hal.digital_output(OutputSpec(pin=17, active_low=True))

        (request,) = chip.requests
        settings = request.config[17]
        assert request.consumer == "primum"
        assert settings.direction == Direction.OUTPUT
        assert settings.output_value == Value.INACTIVE
        assert settings.active_low


def test_set_writes_active_and_inactive_values(chip: FakeChip) -> None:
    with GpiodHal(CHIP) as hal:
        output = hal.digital_output(OutputSpec(pin=17))

        output.set(True)
        assert output.read()
        output.set(False)

        assert chip.requests[0].writes == [(17, Value.ACTIVE), (17, Value.INACTIVE)]


def test_close_writes_the_safe_state_releases_the_line_and_closes_the_chip(
    chip: FakeChip,
) -> None:
    hal = GpiodHal(CHIP)
    hal.digital_output(OutputSpec(pin=17)).set(True)

    hal.close()

    assert chip.requests[0].writes[-1] == (17, Value.INACTIVE)
    assert chip.requests[0].released
    assert chip.closed


def test_offset_the_chip_does_not_have_raises_pin_invalid(chip: FakeChip) -> None:
    with GpiodHal(CHIP) as hal, pytest.raises(PrimumError) as raised:
        hal.digital_output(OutputSpec(pin=NUM_LINES))

    assert raised.value.code == "hal.pin_invalid"
    assert raised.value.params == {"pin": NUM_LINES, "chip": CHIP, "lines": NUM_LINES}
    assert chip.requests == []


def test_line_used_by_another_consumer_raises_pin_unavailable_without_requesting_it(
    chip: FakeChip,
) -> None:
    chip.owners[2] = "kernel"  # GPIO 2 is I2C SDA on a Pi 4 with I2C enabled

    with GpiodHal(CHIP) as hal, pytest.raises(PrimumError) as raised:
        hal.digital_output(OutputSpec(pin=2))

    assert raised.value.code == "hal.pin_unavailable"
    assert raised.value.params == {"pin": 2, "chip": CHIP, "consumer": "kernel"}
    assert chip.requests == []


def test_einval_from_the_request_raises_pin_unavailable(chip: FakeChip) -> None:
    # What gpiod raises on a Pi 4 for GPIO 2 owned by the kernel, if the check missed it.
    chip.request_error = ValueError(errno.EINVAL, "Invalid argument")

    with GpiodHal(CHIP) as hal, pytest.raises(PrimumError) as raised:
        hal.digital_output(OutputSpec(pin=2))

    assert raised.value.code == "hal.pin_unavailable"
    assert raised.value.params["pin"] == 2
    assert isinstance(raised.value.__cause__, ValueError)


def test_busy_line_raises_pin_unavailable_with_the_system_text(chip: FakeChip) -> None:
    chip.request_error = OSError(errno.EBUSY, "Device or resource busy")

    with GpiodHal(CHIP) as hal, pytest.raises(PrimumError) as raised:
        hal.digital_output(OutputSpec(pin=17))

    assert raised.value.code == "hal.pin_unavailable"
    assert raised.value.params == {"pin": 17, "chip": CHIP, "detail": "Device or resource busy"}
    assert isinstance(raised.value.__cause__, OSError)


@pytest.mark.usefixtures("chip")
def test_missing_chip_raises_chip_unavailable_when_the_hal_is_created() -> None:
    with pytest.raises(PrimumError) as raised:
        GpiodHal("/dev/gpiochip-missing")

    assert raised.value.code == "hal.chip_unavailable"
    assert raised.value.params == {
        "chip": "/dev/gpiochip-missing",
        "detail": "No such file or directory",
    }


def test_chip_without_permission_raises_chip_access_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied(_path: str) -> FakeChip:
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(gpiod, "Chip", denied)

    with pytest.raises(PrimumError) as raised:
        GpiodHal(CHIP)

    assert raised.value.code == "hal.chip_access_denied"
    assert raised.value.params == {"chip": CHIP, "detail": "Permission denied"}


def test_create_hal_returns_the_gpio_hal_for_the_chip(chip: FakeChip) -> None:
    with create_hal(simulate=False, chip=CHIP) as hal:
        assert isinstance(hal, GpiodHal)
        hal.digital_output(OutputSpec(pin=17))

    assert chip.requests
