import pytest

from primum_runtime.board import load_board
from primum_runtime.config import BUTTON, DEFAULT_HOST, DEFAULT_PORT, LED, parse_config
from primum_runtime.drivers import ElementConfig


def test_options_build_the_configuration_with_defaults() -> None:
    config = parse_config(["--simulate", "--pin", "17"], {})

    assert config.simulate
    assert config.board == load_board("rpi4b")
    assert config.elements == (ElementConfig(LED, "digital_output", 17, active_low=False),)
    assert config.limits == {("pwm_output", "frequencyHz"): (1, 100_000)}
    assert (config.host, config.port) == (DEFAULT_HOST, DEFAULT_PORT)


def test_environment_variables_configure_the_service() -> None:
    env = {
        "PRIMUM_SIMULATE": "true",
        "PRIMUM_PIN": "22",
        "PRIMUM_ACTIVE_LOW": "1",
        "PRIMUM_BOARD": "rpi4b",
        "PRIMUM_HOST": "0.0.0.0",  # noqa: S104 (a value under test, nothing listens)
        "PRIMUM_PORT": "9000",
    }

    config = parse_config([], env)

    assert config.simulate
    assert config.elements == (ElementConfig(LED, "digital_output", 22, active_low=True),)
    assert config.board.model == "rpi4b"
    assert (config.host, config.port) == ("0.0.0.0", 9000)  # noqa: S104


def test_options_win_over_the_environment() -> None:
    config = parse_config(
        ["--pin", "27", "--no-simulate"], {"PRIMUM_PIN": "22", "PRIMUM_SIMULATE": "1"}
    )

    assert not config.simulate
    assert config.elements[0].pin == 27


def test_missing_pin_exits_with_usage_instead_of_assuming_one() -> None:
    with pytest.raises(SystemExit):
        parse_config(["--simulate"], {})


@pytest.mark.parametrize(
    "env", [{"PRIMUM_PIN": "seventeen"}, {"PRIMUM_PIN": "17", "PRIMUM_SIMULATE": "maybe"}]
)
def test_invalid_environment_values_exit(env: dict[str, str]) -> None:
    with pytest.raises(SystemExit):
        parse_config([], env)


@pytest.mark.parametrize(
    ("argv", "env"), [(["--board", "rpi9"], {}), ([], {"PRIMUM_BOARD": "rpi9"})]
)
def test_a_board_without_a_profile_exits_with_usage(argv: list[str], env: dict[str, str]) -> None:
    with pytest.raises(SystemExit):
        parse_config(["--pin", "17", *argv], env)


def test_an_input_is_listened_to_when_its_pin_and_its_pull_are_given() -> None:
    argv = ["--pin", "17", "--input-pin", "22", "--input-pull", "up", "--input-active-low"]

    config = parse_config(argv, {})

    assert config.elements[1] == ElementConfig(
        BUTTON, "digital_input", 22, active_low=True, options={"pull": "up"}
    )


def test_the_input_comes_from_the_environment_too_with_its_debounce() -> None:
    env = {"PRIMUM_INPUT_PIN": "22", "PRIMUM_INPUT_PULL": "none"}
    env["PRIMUM_INPUT_DEBOUNCE_MS"] = "50"

    config = parse_config(["--pin", "17"], env)

    assert config.elements[1].options == {"pull": "none", "debounceMs": 50}


def test_an_input_without_its_pull_exits_instead_of_assuming_one() -> None:
    with pytest.raises(SystemExit):
        parse_config(["--pin", "17", "--input-pin", "22"], {})


def test_a_pull_that_is_not_one_exits() -> None:
    with pytest.raises(SystemExit):
        parse_config(["--pin", "17", "--input-pin", "22", "--input-pull", "sideways"], {})


def test_a_pull_without_an_input_exits_instead_of_being_ignored() -> None:
    with pytest.raises(SystemExit):
        parse_config(["--pin", "17", "--input-pull", "up"], {})
