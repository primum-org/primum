import pytest

from primum_runtime.config import DEFAULT_HOST, DEFAULT_PORT, LED, parse_config
from primum_runtime.hal import OutputSpec


def test_options_build_the_configuration_with_defaults() -> None:
    config = parse_config(["--simulate", "--pin", "17"], {})

    assert config.simulate
    assert config.chip is None
    assert config.outputs == {LED: OutputSpec(pin=17)}
    assert (config.host, config.port) == (DEFAULT_HOST, DEFAULT_PORT)


def test_environment_variables_configure_the_service() -> None:
    env = {
        "PRIMUM_SIMULATE": "true",
        "PRIMUM_PIN": "22",
        "PRIMUM_ACTIVE_LOW": "1",
        "PRIMUM_CHIP": "/dev/gpiochip4",
        "PRIMUM_HOST": "0.0.0.0",  # noqa: S104 (a value under test, nothing listens)
        "PRIMUM_PORT": "9000",
    }

    config = parse_config([], env)

    assert config.simulate
    assert config.outputs == {LED: OutputSpec(pin=22, active_low=True)}
    assert config.chip == "/dev/gpiochip4"
    assert (config.host, config.port) == ("0.0.0.0", 9000)  # noqa: S104


def test_options_win_over_the_environment() -> None:
    config = parse_config(
        ["--pin", "27", "--no-simulate"], {"PRIMUM_PIN": "22", "PRIMUM_SIMULATE": "1"}
    )

    assert not config.simulate
    assert config.outputs[LED].pin == 27


def test_missing_pin_exits_with_usage_instead_of_assuming_one() -> None:
    with pytest.raises(SystemExit):
        parse_config(["--simulate"], {})


@pytest.mark.parametrize(
    "env", [{"PRIMUM_PIN": "seventeen"}, {"PRIMUM_PIN": "17", "PRIMUM_SIMULATE": "maybe"}]
)
def test_invalid_environment_values_exit(env: dict[str, str]) -> None:
    with pytest.raises(SystemExit):
        parse_config([], env)
