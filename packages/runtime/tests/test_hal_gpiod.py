"""GpiodHal without a Pi: `gpiod.request_lines` is replaced by a fake that records the calls.

The real kernel interaction is covered by the `hw` test on the Pi; these tests cover our side:
the requested configuration, the values written, the release and the error mapping.
"""

import errno
from dataclasses import dataclass, field

import pytest

from primum_runtime.errors import PrimumError
from primum_runtime.hal import OutputSpec, create_hal

gpiod = pytest.importorskip("gpiod", reason="gpiod is only installed on Linux")
from gpiod import LineSettings  # noqa: E402 (after the importorskip above)
from gpiod.line import Direction, Value  # noqa: E402

from primum_runtime.hal.gpiod_hal import GpiodHal  # noqa: E402 (needs gpiod)

CHIP = "/dev/gpiochip7"


@dataclass
class FakeRequest:
    """Stands in for `gpiod.LineRequest`: records what the HAL asks of the line."""

    path: str
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


@pytest.fixture
def requests(monkeypatch: pytest.MonkeyPatch) -> list[FakeRequest]:
    made: list[FakeRequest] = []

    def request_lines(
        path: str, config: dict[int, LineSettings], consumer: str | None = None
    ) -> FakeRequest:
        request = FakeRequest(path, consumer, config)
        made.append(request)
        return request

    monkeypatch.setattr(gpiod, "request_lines", request_lines)
    return made


def test_output_requests_one_inactive_output_line(requests: list[FakeRequest]) -> None:
    with GpiodHal(CHIP) as hal:
        hal.digital_output(OutputSpec(pin=17, active_low=True))

        (request,) = requests
        settings = request.config[17]
        assert request.path == CHIP
        assert request.consumer == "primum"
        assert settings.direction == Direction.OUTPUT
        assert settings.output_value == Value.INACTIVE
        assert settings.active_low


def test_set_writes_active_and_inactive_values(requests: list[FakeRequest]) -> None:
    with GpiodHal(CHIP) as hal:
        output = hal.digital_output(OutputSpec(pin=17))

        output.set(True)
        assert output.read()
        output.set(False)

        assert requests[0].writes == [(17, Value.ACTIVE), (17, Value.INACTIVE)]


def test_close_writes_the_safe_state_and_releases_the_line(requests: list[FakeRequest]) -> None:
    hal = GpiodHal(CHIP)
    hal.digital_output(OutputSpec(pin=17)).set(True)

    hal.close()

    assert requests[0].writes[-1] == (17, Value.INACTIVE)
    assert requests[0].released


def test_unavailable_line_raises_pin_unavailable_with_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def busy(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.EBUSY, "Device or resource busy")

    monkeypatch.setattr(gpiod, "request_lines", busy)

    with GpiodHal(CHIP) as hal, pytest.raises(PrimumError) as raised:
        hal.digital_output(OutputSpec(pin=17))

    assert raised.value.code == "hal.pin_unavailable"
    assert raised.value.params == {"pin": 17, "chip": CHIP, "detail": "Device or resource busy"}
    assert isinstance(raised.value.__cause__, OSError)


def test_offset_the_chip_does_not_have_raises_pin_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # What gpiod raises on a Pi 4 for OutputSpec(pin=99) on gpiochip0.
    def out_of_range(*_args: object, **_kwargs: object) -> None:
        raise ValueError("line offset of out range")

    monkeypatch.setattr(gpiod, "request_lines", out_of_range)

    with GpiodHal(CHIP) as hal, pytest.raises(PrimumError) as raised:
        hal.digital_output(OutputSpec(pin=99))

    assert raised.value.code == "hal.pin_invalid"
    assert raised.value.params == {"pin": 99, "chip": CHIP, "detail": "line offset of out range"}
    assert isinstance(raised.value.__cause__, ValueError)


def test_create_hal_returns_the_gpio_hal_for_the_chip(requests: list[FakeRequest]) -> None:
    with create_hal(simulate=False, chip=CHIP) as hal:
        assert isinstance(hal, GpiodHal)
        hal.digital_output(OutputSpec(pin=17))

    assert requests[0].path == CHIP
