from primum_runtime.errors import PrimumError


def test_str_shows_the_code_and_params_for_logs() -> None:
    error = PrimumError("hal.pin_invalid", {"pin": 99, "chip": "/dev/gpiochip0"})

    assert str(error) == "hal.pin_invalid (pin=99, chip=/dev/gpiochip0)"


def test_str_without_params_is_the_code() -> None:
    assert str(PrimumError("hal.closed")) == "hal.closed"
