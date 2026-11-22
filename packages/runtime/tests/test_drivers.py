"""The three drivers, each against the simulated HAL, as their manifests describe them."""

from dataclasses import replace

import pytest

from primum_core.generated.model import Driver
from primum_runtime.board import load_board, load_profile, option_limits
from primum_runtime.drivers import (
    DRIVERS,
    DigitalInputDriver,
    DigitalOutputDriver,
    ElementConfig,
    ElementDriver,
    OutputDriver,
    PwmOutputDriver,
    create_driver,
    load_manifests,
)
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.hal import Claim, InputSpec, OutputSpec, Pull, PwmSpec, SimulatedHal

BOARD = load_board("rpi4b")
LIMITS = option_limits(load_profile("rpi4b"))
MANIFESTS = load_manifests()

LED = ElementConfig("led", "digital_output", 17, active_low=False)
DIMMER = ElementConfig("dimmer", "pwm_output", 18, active_low=False)
BUTTON = ElementConfig("button", "digital_input", 22, active_low=True, options={"pull": "up"})


def _claimed(driver: ElementDriver) -> SimulatedHal:
    """A HAL that has claimed what the driver asks for, the driver bound to it."""
    hal = SimulatedHal(BOARD)
    spec = driver.spec
    hal.claim(
        Claim(
            outputs=[spec] if isinstance(spec, OutputSpec) else [],
            inputs=[spec] if isinstance(spec, InputSpec) else [],
            pwms=[spec] if isinstance(spec, PwmSpec) else [],
        )
    )
    driver.bind(hal)
    return hal


def _safe_state(manifest: Driver) -> str:
    assert manifest.safe_state is not None
    return manifest.safe_state


def _output(element: ElementConfig) -> tuple[OutputDriver, SimulatedHal]:
    driver = create_driver(element, MANIFESTS, LIMITS)
    assert isinstance(driver, OutputDriver)
    return driver, _claimed(driver)


def _button(**options: object) -> tuple[DigitalInputDriver, SimulatedHal]:
    element = replace(BUTTON, options={**BUTTON.options, **options})
    driver = create_driver(element, MANIFESTS, LIMITS)
    assert isinstance(driver, DigitalInputDriver)
    return driver, _claimed(driver)


def test_every_shipped_manifest_has_a_driver_and_every_driver_a_manifest() -> None:
    assert set(DRIVERS) == set(MANIFESTS)


def test_each_element_gets_the_driver_of_its_type() -> None:
    kinds = [type(create_driver(element, MANIFESTS, LIMITS)) for element in (LED, DIMMER, BUTTON)]

    assert kinds == [DigitalOutputDriver, PwmOutputDriver, DigitalInputDriver]


def test_a_type_without_a_driver_is_refused() -> None:
    sensor = ElementConfig("sensor", "i2c_device", 2, active_low=False)

    with pytest.raises(PrimumError) as raised:
        create_driver(sensor, MANIFESTS, LIMITS)

    assert raised.value.code == "element.type_unsupported"
    assert raised.value.params == {"element": "sensor", "type": "i2c_device"}


# --- digital_output ----------------------------------------------------------------------


def test_a_digital_output_asks_for_its_pin_as_it_is_wired() -> None:
    driver = create_driver(replace(LED, active_low=True), MANIFESTS, LIMITS)

    assert driver.spec == OutputSpec(pin=17, active_low=True)


def test_a_digital_output_goes_on_and_off() -> None:
    driver, hal = _output(LED)

    driver.command("on")
    assert hal.lines[17].active
    assert driver.level == 100

    driver.command("off")
    assert not hal.lines[17].active
    assert driver.level == 0


def test_a_digital_output_takes_no_options() -> None:
    with pytest.raises(PrimumError) as raised:
        create_driver(replace(LED, options={"frequencyHz": 1000}), MANIFESTS, LIMITS)

    assert raised.value.code == "element.value_unknown"
    assert raised.value.params == {"element": "led", "name": "frequencyHz"}


# --- pwm_output --------------------------------------------------------------------------


def test_a_pwm_output_asks_for_its_frequency_or_the_default_of_its_manifest() -> None:
    default = create_driver(DIMMER, MANIFESTS, LIMITS)
    given = create_driver(replace(DIMMER, options={"frequencyHz": 25_000}), MANIFESTS, LIMITS)

    assert default.spec == PwmSpec(pin=18, frequency_hz=1000)
    assert given.spec == PwmSpec(pin=18, frequency_hz=25_000)


@pytest.mark.parametrize(
    ("action", "arguments", "duty"),
    [
        ("on", {}, 1.0),
        ("off", {}, 0.0),
        ("set", {"level": 25}, 0.25),
        ("set", {"level": 12.5}, 0.125),
        ("fade", {"from": 100, "to": 40}, 0.4),  # as an instant command it jumps to its end
        ("fade", {"to": 40}, 0.4),  # its ``from`` may be left out: from where it is
    ],
)
def test_a_pwm_output_goes_to_the_level_each_action_ends_in(
    action: str, arguments: dict[str, float], duty: float
) -> None:
    driver, hal = _output(DIMMER)
    driver.command("set", {"level": 50})

    driver.command(action, arguments)

    assert hal.pwm_lines[18].duty == duty
    assert driver.level == duty * 100


@pytest.mark.parametrize("frequency", [1, 100_000])
def test_a_pwm_output_takes_both_ends_of_what_its_board_takes(frequency: int) -> None:
    driver = create_driver(replace(DIMMER, options={"frequencyHz": frequency}), MANIFESTS, LIMITS)

    assert driver.spec == PwmSpec(pin=18, frequency_hz=frequency)


@pytest.mark.parametrize("frequency", [0, 100_001])
def test_a_frequency_the_board_does_not_take_is_refused_by_the_driver(frequency: int) -> None:
    with pytest.raises(PrimumError) as raised:
        create_driver(replace(DIMMER, options={"frequencyHz": frequency}), MANIFESTS, LIMITS)

    assert raised.value.code == "element.value_out_of_range"
    assert raised.value.params == {
        "element": "dimmer",
        "name": "frequencyHz",
        "min": 1,
        "max": 100_000,
    }


def test_on_another_board_the_same_frequency_may_be_fine() -> None:
    other = {("pwm_output", "frequencyHz"): (1.0, 500_000.0)}

    driver = create_driver(replace(DIMMER, options={"frequencyHz": 200_000}), MANIFESTS, other)

    assert driver.spec == PwmSpec(pin=18, frequency_hz=200_000)


@pytest.mark.parametrize(
    ("arguments", "code", "params"),
    [
        ({}, "element.value_missing", {"name": "level"}),
        ({"level": 101}, "element.value_out_of_range", {"name": "level", "min": 0, "max": 100}),
        ({"level": "high"}, "element.value_invalid", {"name": "level"}),
        ({"level": 5, "speed": 2}, "element.value_unknown", {"name": "speed"}),
    ],
)
def test_arguments_an_action_does_not_take_as_given_change_nothing(
    arguments: dict[str, float | str], code: str, params: dict[str, object]
) -> None:
    driver, hal = _output(DIMMER)

    with pytest.raises(PrimumError) as raised:
        driver.command("set", arguments)

    assert raised.value.code == code
    assert raised.value.params == {"element": "dimmer", **params}
    assert hal.pwm_lines[18].history == ()


def test_a_level_read_back_within_one_step_is_the_level_written() -> None:
    """At 1 kHz the period is a million nanoseconds: a third reads back as 0.333333."""
    driver, hal = _output(DIMMER)

    driver.command("set", {"level": 100 / 3})

    assert hal.pwm_lines[18].read() == 0.333333


def test_at_the_highest_frequency_a_level_under_one_step_does_not_pass_for_another() -> None:
    """At 100 kHz a step is 0.01: 0.004 rounds to 0 and is within a step of it, 0.02 is not."""
    fast = replace(DIMMER, options={"frequencyHz": 100_000})
    driver, hal = _output(fast)

    driver.command("set", {"level": 0.004})
    assert hal.pwm_lines[18].read() == 0.0

    hal.pwm_lines[18].stick(0.0)
    with pytest.raises(PrimumError) as raised:
        driver.command("set", {"level": 0.02})
    assert raised.value.code == "element.level_not_reached"


def test_a_level_under_one_step_is_reported_as_the_0_the_pin_gets() -> None:
    """At 1 kHz a step is a millionth: a hundred-millionth of a level rounds to 0 ns."""
    driver, hal = _output(DIMMER)

    driver.command("set", {"level": 1e-8})

    assert hal.pwm_lines[18].read() == 0.0
    assert driver.level == 0.0


def test_a_number_that_nothing_limits_is_refused_by_the_driver_too() -> None:
    """As ``core`` does: without the board's limit any frequency would reach the HAL."""
    with pytest.raises(PrimumError) as raised:
        create_driver(replace(DIMMER, options={"frequencyHz": 20_000_000}), MANIFESTS, {})

    assert raised.value.code == "element.value_unlimited"
    assert raised.value.params == {"element": "dimmer", "name": "frequencyHz"}


def test_an_argument_that_nothing_limits_is_refused() -> None:
    level = replace(MANIFESTS["pwm_output"].actions[2].parameters[0], min=None, max=None)
    action = replace(MANIFESTS["pwm_output"].actions[2], parameters=(level,))
    manifest = replace(MANIFESTS["pwm_output"], actions=(action,), safe_state=None)
    driver = create_driver(DIMMER, {"pwm_output": manifest}, LIMITS)
    assert isinstance(driver, OutputDriver)
    hal = _claimed(driver)

    with pytest.raises(PrimumError) as raised:
        driver.command("set", {"level": 5})

    assert raised.value.code == "element.value_unlimited"
    assert hal.pwm_lines[18].history == ()


def test_a_level_read_back_further_than_one_step_is_an_error() -> None:
    driver, hal = _output(DIMMER)
    hal.pwm_lines[18].stick(0.33)

    with pytest.raises(PrimumError) as raised:
        driver.command("set", {"level": 100 / 3})

    assert raised.value.code == "element.level_not_reached"
    assert raised.value.params == {"element": "dimmer", "level": 100 / 3, "read": 33.0}


# --- the safe state of each manifest is the HAL's ------------------------------------------


@pytest.mark.parametrize("element", [LED, DIMMER], ids=lambda element: element.type)
def test_the_safe_state_of_the_manifest_leaves_the_hal_where_its_own_does(
    element: ElementConfig,
) -> None:
    by_driver, by_hal = _output(element), _output(element)
    for driver, _ in (by_driver, by_hal):
        driver.command("on")

    by_driver[0].command(_safe_state(MANIFESTS[element.type]))
    by_hal[1].apply_safe_state()

    for _, hal in (by_driver, by_hal):
        assert [line.active for line in hal.lines.values()] == [False] * len(hal.lines)
        assert [line.duty for line in hal.pwm_lines.values()] == [0.0] * len(hal.pwm_lines)


@pytest.mark.parametrize("kind", ["digital_output", "pwm_output"])
def test_a_safe_state_that_is_not_the_hal_s_would_be_seen(kind: str) -> None:
    """The test above is not vacuous: with ``on`` as the safe state it tells them apart."""
    manifest: Driver = replace(MANIFESTS[kind], safe_state="on")
    element = LED if kind == "digital_output" else DIMMER
    driver = create_driver(element, {kind: manifest}, LIMITS)
    assert isinstance(driver, OutputDriver)
    hal = _claimed(driver)

    driver.command(_safe_state(manifest))

    assert [line.active for line in hal.lines.values()] == [True] * len(hal.lines)
    assert [line.duty for line in hal.pwm_lines.values()] == [1.0] * len(hal.pwm_lines)


# --- digital_input -----------------------------------------------------------------------


def test_an_input_hands_the_hal_every_option_with_the_default_of_its_manifest() -> None:
    driver, _ = _button()

    assert driver.spec == InputSpec(pin=22, pull=Pull.UP, active_low=True, debounce_ms=20)


def test_an_input_hands_the_hal_the_options_its_element_gives() -> None:
    driver, _ = _button(pull="none", debounceMs=0)

    assert driver.spec == InputSpec(pin=22, pull=Pull.NONE, active_low=True, debounce_ms=0)


def test_an_input_without_its_pull_is_refused() -> None:
    with pytest.raises(PrimumError) as raised:
        create_driver(replace(BUTTON, options={}), MANIFESTS, LIMITS)

    assert raised.value.code == "element.value_missing"
    assert raised.value.params == {"element": "button", "name": "pull"}


@pytest.mark.parametrize("debounce", [-1, 10_001])
def test_a_debounce_outside_the_limits_of_the_manifest_is_refused(debounce: int) -> None:
    with pytest.raises(PrimumError) as raised:
        _button(debounceMs=debounce)

    assert raised.value.code == "element.value_out_of_range"
    assert raised.value.params == {
        "element": "button",
        "name": "debounceMs",
        "min": 0,
        "max": 10_000,
    }


def test_whole_limits_are_shown_without_decimals() -> None:
    with pytest.raises(PrimumError) as raised:
        _button(debounceMs=-1)

    assert [repr(raised.value.params[key]) for key in ("min", "max")] == ["0", "10000"]


def test_a_pull_that_is_not_one_is_refused() -> None:
    with pytest.raises(PrimumError) as raised:
        _button(pull="sideways")

    assert raised.value.code == "element.value_invalid"


def test_an_input_follows_its_events() -> None:
    driver, hal = _button()
    hal.simulate_input(22, True)
    hal.simulate_input(22, False)
    hal.simulate_input(22, True)

    changes = [driver.handle(event) for event in hal.read_events()]

    assert changes == [True, True, True]
    assert driver.active
    assert driver.lost_events == 0


def test_an_input_starts_in_the_state_its_line_is_in() -> None:
    hal = SimulatedHal(BOARD)
    driver = create_driver(BUTTON, MANIFESTS, LIMITS)
    assert isinstance(driver, DigitalInputDriver)
    hal.claim(Claim(inputs=[driver.spec]))
    hal.simulate_input(22, True)
    hal.read_events()

    driver.bind(hal)

    assert driver.active


def test_two_events_of_the_same_kind_do_not_flip_the_state() -> None:
    """A pulse too short gives two equal events: the state is the event's, not a toggle."""
    driver, hal = _button()
    hal.simulate_event(22, True)
    hal.simulate_event(22, True)

    changes = [driver.handle(event) for event in hal.read_events()]

    assert changes == [True, False]
    assert driver.active


def test_lost_events_are_counted_and_the_state_is_still_right(
    caplog: pytest.LogCaptureFixture,
) -> None:
    driver, hal = _button()
    for number in range(7):
        hal.simulate_input(22, number % 2 == 0)
    hal.lose_events(4)

    for event in hal.read_events():
        driver.handle(event)

    assert driver.lost_events == 4
    assert driver.active  # the seventh change was to active
    assert "lost 4 events" in caplog.text


def test_a_pwm_output_wired_active_low_is_refused_by_its_driver() -> None:
    """The driver writes the duty as it is, so active low would rest fully on: it says so
    instead of taking a wiring it does not carry out."""
    with pytest.raises(PrimumError) as refused:
        create_driver(replace(DIMMER, active_low=True), MANIFESTS, LIMITS)

    assert (refused.value.code, dict(refused.value.params)) == (
        ErrorCode.ELEMENT_ACTIVE_LOW_UNSUPPORTED,
        {"element": "dimmer", "type": "pwm_output"},
    )
