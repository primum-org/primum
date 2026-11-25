"""Loading a deployment package: what the runtime checks against its drivers and its board
before it runs one, and the service that starts from it."""

import json
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import cast

import pytest
from fastapi.testclient import TestClient

from primum_core.compiler import compile_package
from primum_core.formats import read_driver
from primum_core.package import package_hash
from primum_core.workspace import load_workspace
from primum_runtime.api import app, create_app
from primum_runtime.board import load_board, load_profile
from primum_runtime.cli import EXIT_FAILED, main
from primum_runtime.config import parse_config
from primum_runtime.drivers import ElementConfig, load_manifests
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.hal import BoardGpio, Claim, SimulatedHal
from primum_runtime.package import load_package

ROOT = Path(__file__).resolve().parents[3]
SHOP = ROOT / "examples" / "shop-window"
MANIFESTS = load_manifests()
RELAY, LED, SENSOR = (
    "4e6c4a57-3921-4ed7-98e6-26fa70e33ad4",
    "abe91183-5c31-49cb-8a09-78c78f8705f5",
    "019556e9-6666-48d0-a08a-468b54b30c43",
)

type Document = dict[str, object]
type Change = Callable[[Document], None]


def _shop() -> Document:
    """The deployment package of the shop-window example, as its document."""
    files = {
        PurePosixPath(path.relative_to(SHOP).as_posix()): path.read_bytes()
        for path in SHOP.rglob("*")
        if path.is_file()
    }
    workspace = load_workspace(files, {"rpi4b": load_profile("rpi4b")}, MANIFESTS).value
    assert workspace is not None
    document = compile_package(workspace).value
    assert document is not None
    return document


def _written(tmp_path: Path, change: Change | None = None) -> Path:
    """The shop-window package in a file, changed by hand if asked and its hash made right."""
    document = _shop()
    if change is not None:
        change(document)
        document["hash"] = package_hash(document)
    path = tmp_path / "shop.package.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _inside(document: Document, *path: str | int) -> Document:
    found: object = document
    for step in path:
        found = cast("dict[str | int, object]", found)[step]
    return cast("Document", found)


def _refused(tmp_path: Path, change: Change) -> PrimumError:
    with pytest.raises(PrimumError) as refused:
        load_package(_written(tmp_path, change), MANIFESTS)
    return refused.value


def _welcome_fade(document: Document) -> Document:
    """The command of *Welcome* that fades the LED up to ``brightness``."""
    sequences = cast("list[Document]", document["sequences"])
    welcome = next(sequence for sequence in sequences if sequence["name"] == "Welcome")
    return cast("list[Document]", welcome["commands"])[1]


def test_a_package_gives_its_elements_by_id_as_their_drivers_take_them(tmp_path: Path) -> None:
    loaded = load_package(_written(tmp_path), MANIFESTS)

    assert loaded.package.project.name == "Shop window"
    assert loaded.elements == (
        ElementConfig("Sign relay", "digital_output", 27, active_low=True, id=RELAY),
        ElementConfig("Window LED", "pwm_output", 18, False, {"frequencyHz": 500}, LED),
        ElementConfig(
            "Presence sensor",
            "digital_input",
            22,
            False,
            {"pull": "none", "debounceMs": 100},
            SENSOR,
        ),
    )


def test_a_file_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PrimumError) as refused:
        load_package(tmp_path / "nothing.package.json", MANIFESTS)

    assert refused.value.code is ErrorCode.PACKAGE_UNREADABLE
    assert refused.value.params["path"] == str(tmp_path / "nothing.package.json")


def test_a_package_that_core_refuses_is_refused_with_what_core_found(tmp_path: Path) -> None:
    path = _written(tmp_path)
    path.write_text(path.read_text().replace("Shop window", "Another"), encoding="utf-8")

    with pytest.raises(PrimumError) as refused:
        load_package(path, MANIFESTS)

    assert refused.value.code is ErrorCode.PACKAGE_INVALID
    assert refused.value.params == {
        "path": str(path),
        "problems": ("package.hash_mismatch",),
        "pointers": ("/hash",),
    }


def test_a_package_for_a_board_without_a_profile_is_refused(tmp_path: Path) -> None:
    error = _refused(tmp_path, lambda d: _inside(d, "board").update(model="rpi9"))

    assert (error.code, dict(error.params)) == (
        ErrorCode.PACKAGE_BOARD_UNSUPPORTED,
        {"board": "rpi9", "available": ("rpi4b",)},
    )


def test_an_element_of_a_type_without_a_driver_is_refused(tmp_path: Path) -> None:
    error = _refused(tmp_path, lambda d: _inside(d, "elements", 0).update(type="servo"))

    assert (error.code, dict(error.params)) == (
        ErrorCode.ELEMENT_TYPE_UNSUPPORTED,
        {"element": "Sign relay", "type": "servo", "id": RELAY},
    )


def test_an_option_the_board_does_not_take_is_refused(tmp_path: Path) -> None:
    def too_fast(document: Document) -> None:
        _inside(document, "elements", 1, "config", 0)["value"] = 200_000

    error = _refused(tmp_path, too_fast)

    assert error.code is ErrorCode.ELEMENT_VALUE_OUT_OF_RANGE
    assert (error.params["element"], error.params["name"]) == ("Window LED", "frequencyHz")


def test_an_option_its_driver_does_not_have_is_refused(tmp_path: Path) -> None:
    def extra(document: Document) -> None:
        options = cast("list[object]", _inside(document, "elements", 0)["config"])
        options.append({"name": "speed", "value": 3})

    assert _refused(tmp_path, extra).code is ErrorCode.ELEMENT_VALUE_UNKNOWN


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"action": "blink"}, ErrorCode.ELEMENT_ACTION_UNKNOWN),
        ({"arguments": [{"name": "to", "value": 150}]}, ErrorCode.ELEMENT_VALUE_OUT_OF_RANGE),
        ({"arguments": [{"name": "to", "value": "high"}]}, ErrorCode.ELEMENT_VALUE_INVALID),
        ({"arguments": []}, ErrorCode.ELEMENT_VALUE_MISSING),
        (
            {"arguments": [{"name": "to", "value": 5}, {"name": "speed", "value": 1}]},
            ErrorCode.ELEMENT_VALUE_UNKNOWN,
        ),
    ],
)
def test_a_command_its_driver_cannot_carry_out_is_refused(
    tmp_path: Path, change: Document, code: ErrorCode
) -> None:
    error = _refused(tmp_path, lambda d: _welcome_fade(d).update(change))

    assert error.code is code
    assert error.params["element"] == "Window LED"


def test_a_command_on_an_element_that_takes_none_is_refused(tmp_path: Path) -> None:
    error = _refused(tmp_path, lambda d: _welcome_fade(d).update(element=SENSOR))

    assert (error.code, error.params["element"]) == (
        ErrorCode.ELEMENT_ACTION_UNKNOWN,
        "Presence sensor",
    )


def _brightness(document: Document) -> Document:
    variables = cast("list[Document]", document["variables"])
    return next(variable for variable in variables if variable["name"] == "brightness")


@pytest.mark.parametrize(
    "change",
    [{"max": 500, "initial": 80}, {"type": "boolean", "initial": True, "min": None, "max": None}],
    ids=["limits beyond the parameter's", "another type"],
)
def test_a_variable_that_may_not_fit_the_parameter_it_is_read_for_is_refused(
    tmp_path: Path, change: Document
) -> None:
    def unfit(document: Document) -> None:
        variable = _brightness(document)
        for key, value in change.items():
            if value is None:
                del variable[key]
            else:
                variable[key] = value

    error = _refused(tmp_path, unfit)

    assert (error.code, dict(error.params)) == (
        ErrorCode.ELEMENT_VARIABLE_UNFIT,
        {
            "element": "Window LED",
            "action": "fade",
            "name": "to",
            "variable": "brightness",
            "id": LED,
        },
    )


def test_a_variable_read_for_a_parameter_the_action_does_not_have_is_refused(
    tmp_path: Path,
) -> None:
    def misnamed(document: Document) -> None:
        arguments = cast("list[Document]", _welcome_fade(document)["arguments"])
        arguments[1]["name"] = "speed"
        arguments.append({"name": "to", "value": 5})

    assert _refused(tmp_path, misnamed).code is ErrorCode.ELEMENT_VALUE_UNKNOWN


# --- the configuration ---------------------------------------------------------------------


def test_a_package_configures_the_service_with_its_board_and_its_elements(tmp_path: Path) -> None:
    path = _written(tmp_path)

    config = parse_config(["--simulate", "--no-pairing", "--package", str(path)], {})

    assert config.board == load_board("rpi4b")
    assert [element.key for element in config.elements] == [RELAY, LED, SENSOR]
    assert config.package is not None
    assert config.package.hash == _shop()["hash"]


def test_the_package_may_come_from_the_environment(tmp_path: Path) -> None:
    config = parse_config([], {"PRIMUM_PACKAGE": str(_written(tmp_path)), "PRIMUM_SIMULATE": "1"})

    assert config.package is not None


@pytest.mark.parametrize(
    "also",
    [
        ["--pin", "17"],
        ["--active-low"],
        ["--input-pin", "22", "--input-pull", "up"],
        ["--pwm-pin", "18"],
        ["--board", "rpi5"],
    ],
)
def test_a_package_and_options_of_elements_or_another_board_are_refused(
    tmp_path: Path, also: list[str]
) -> None:
    with pytest.raises(SystemExit):
        parse_config(["--simulate", "--package", str(_written(tmp_path)), *also], {})


def test_the_board_of_the_package_may_be_said_again(tmp_path: Path) -> None:
    path = _written(tmp_path)

    assert parse_config(["--package", str(path), "--board", "rpi4b"], {}).package is not None


def test_the_service_does_not_start_from_a_package_it_cannot_run(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = _written(tmp_path, lambda d: _welcome_fade(d).update(action="blink"))

    assert main(["--simulate", "--package", str(path)]) == EXIT_FAILED
    assert "element.action_unknown" in caplog.text


# --- the service ---------------------------------------------------------------------------


def _client(tmp_path: Path, hal: SimulatedHal, change: Change | None = None) -> TestClient:
    config = parse_config(
        ["--simulate", "--no-pairing", "--package", str(_written(tmp_path, change))], {}
    )
    return TestClient(create_app(config, open_hal=lambda: hal))


def test_the_service_reports_the_elements_of_its_package_by_id_and_name(tmp_path: Path) -> None:
    with _client(tmp_path, SimulatedHal(load_board("rpi4b"))) as client:
        state = client.get("/api/status").json()

    assert [(output["id"], output["name"], output["actions"]) for output in state["outputs"]] == [
        (RELAY, "Sign relay", ["on", "off"]),
        (LED, "Window LED", ["on", "off", "set", "fade"]),
    ]
    assert state["inputs"] == [
        {"id": SENSOR, "name": "Presence sensor", "active": False, "lostEvents": 0}
    ]


def test_an_output_of_a_package_is_commanded_by_its_id_on_its_pin(tmp_path: Path) -> None:
    hal = SimulatedHal(load_board("rpi4b"))
    with _client(tmp_path, hal) as client:
        relay = client.put(f"/api/outputs/{RELAY}", json={"action": "on"})
        dimmed = client.put(
            f"/api/outputs/{LED}", json={"action": "set", "arguments": {"level": 40}}
        )
        by_name = client.put("/api/outputs/Sign relay", json={"action": "on"})

        assert relay.status_code == dimmed.status_code == 200
        assert hal.lines[27].active
        assert hal.pwm_lines[18].duty == 0.4
        assert (by_name.status_code, by_name.json()["code"]) == (404, "output.unknown")


class _BusyHal(SimulatedHal):
    """A board where another program holds a line: only the kernel knows, at the claim."""

    def claim(self, claim: Claim) -> None:
        raise PrimumError(ErrorCode.HAL_REQUEST_FAILED, {"pins": (27,), "detail": "busy"})


def test_the_hal_still_refuses_what_only_it_can_tell_and_nothing_is_claimed(
    tmp_path: Path,
) -> None:
    hal = _BusyHal(load_board("rpi4b"))
    with pytest.raises(PrimumError) as refused, _client(tmp_path, hal):
        pass

    assert refused.value.code is ErrorCode.HAL_REQUEST_FAILED
    assert not hal.lines
    assert not hal.pwm_lines


@pytest.mark.parametrize(
    "also",
    [["--pin", "0"], ["--input-debounce-ms", "0"], ["--pwm-frequency-hz", "0"]],
)
def test_an_option_of_elements_given_as_zero_is_given_all_the_same(
    tmp_path: Path, also: list[str]
) -> None:
    """Zero is a pin and a debounce like any other: it is not "not given"."""
    with pytest.raises(SystemExit):
        parse_config(["--simulate", "--package", str(_written(tmp_path)), *also], {})


def test_two_elements_on_one_pin_are_refused_by_name_before_the_hal_is_asked(
    tmp_path: Path,
) -> None:
    def same_pin(document: Document) -> None:
        _inside(document, "elements", 2)["pin"] = 27

    error = _refused(tmp_path, same_pin)

    assert (error.code, dict(error.params)) == (
        ErrorCode.ELEMENT_WIRING_REFUSED,
        {
            "element": "Presence sensor",
            "id": SENSOR,
            "pin": 27,
            "problem": "pin.in_use",
            "other": "Sign relay",
        },
    )


@pytest.mark.parametrize(
    ("element", "change", "problem"),
    [
        (2, {"pin": 0}, "pin.reserved"),  # the EEPROM of a HAT: the HAL would hand it over
        (2, {"pin": 99}, "pin.not_on_board"),
        (1, {"pin": 17}, "pin.function_unavailable"),  # no hardware PWM there
    ],
)
def test_an_element_wired_as_the_board_does_not_allow_is_refused(
    tmp_path: Path, element: int, change: Document, problem: str
) -> None:
    """By the rules ``core`` checks a project with: a package is not trusted to have been
    built from one that passed them."""
    error = _refused(tmp_path, lambda d: _inside(d, "elements", element).update(change))

    assert (error.code, error.params["problem"], error.params["pin"]) == (
        ErrorCode.ELEMENT_WIRING_REFUSED,
        problem,
        change["pin"],
    )


def test_two_pwm_outputs_on_one_channel_are_refused_naming_the_other(tmp_path: Path) -> None:
    def same_channel(document: Document) -> None:
        _inside(document, "elements", 0).update(type="pwm_output", pin=12, activeLow=False)
        _inside(document, "elements", 0)["config"] = [{"name": "frequencyHz", "value": 500}]
        for sequence in cast("list[Document]", document["sequences"]):
            sequence["commands"] = []

    error = _refused(tmp_path, same_channel)

    assert (error.code, error.params["problem"], error.params["other"]) == (
        ErrorCode.ELEMENT_WIRING_REFUSED,
        "pwm.channel_in_use",
        "Sign relay",
    )


def test_everything_wrong_with_a_package_is_logged_and_the_first_is_raised(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def several(document: Document) -> None:
        _inside(document, "elements", 2)["pin"] = 0
        _welcome_fade(document).update(action="blink")
        _inside(document, "elements", 1, "config", 0)["value"] = 200_000

    error = _refused(tmp_path, several)

    assert error.code is ErrorCode.ELEMENT_VALUE_OUT_OF_RANGE  # the first found
    refused = [record.getMessage() for record in caplog.records if "refused" in record.message]
    assert [message.split()[1] for message in refused] == [
        "element.value_out_of_range",
        "element.wiring_refused",
    ]


def test_an_error_about_an_element_says_its_id_since_a_name_may_be_shared(
    tmp_path: Path,
) -> None:
    def twins(document: Document) -> None:
        _inside(document, "elements", 1)["name"] = "Sign relay"
        _welcome_fade(document).update(action="blink")

    error = _refused(tmp_path, twins)

    assert (error.code, error.params["element"], error.params["id"]) == (
        ErrorCode.ELEMENT_ACTION_UNKNOWN,
        "Sign relay",
        LED,
    )


def test_a_variable_for_a_number_that_nothing_limits_is_refused_as_a_written_one_is(
    tmp_path: Path,
) -> None:
    """No shipped manifest has such a parameter; a written value for one is already refused
    (``element.value_unlimited``), and a variable must not be a way around it."""
    unlimited = json.loads((ROOT / "drivers" / "pwm_output.json").read_text())
    fade = next(action for action in unlimited["actions"] if action["name"] == "fade")
    fade["parameters"].append({"name": "speed", "type": "number", "optional": True})
    manifest = read_driver(PurePosixPath("pwm_output.json"), json.dumps(unlimited).encode()).value
    assert manifest is not None
    manifests = {**MANIFESTS, "pwm_output": manifest}

    def reading_it(document: Document, **argument: object) -> None:
        arguments = cast("list[Document]", _welcome_fade(document)["arguments"])
        arguments.append({"name": "speed", **argument})

    def from_a_variable(document: Document) -> None:
        reading_it(document, variable=_brightness(document)["id"])

    def written(document: Document) -> None:
        reading_it(document, value=3)

    refused: list[PrimumError] = []
    for change in (from_a_variable, written):
        with pytest.raises(PrimumError) as error:
            load_package(_written(tmp_path, change), manifests)
        refused.append(error.value)

    assert [(error.code, error.params["name"]) for error in refused] == [
        (ErrorCode.ELEMENT_VALUE_UNLIMITED, "speed"),
        (ErrorCode.ELEMENT_VALUE_UNLIMITED, "speed"),
    ]


def test_a_package_the_hal_refuses_ends_the_service_as_any_other_refusal_does(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refused at the claim, inside the server's startup, where uvicorn exits on its own with
    a status of its own (3): the service gives the same status as for a package refused
    before it, so that whoever supervises it has one to tell "cannot run this" by."""

    def busy(*, simulate: bool, board: BoardGpio) -> SimulatedHal:
        return _BusyHal(board)

    monkeypatch.setattr(app, "create_hal", busy)

    status = main(["--simulate", "--package", str(_written(tmp_path)), "--port", "0"])

    assert status == EXIT_FAILED
    assert "hal.request_failed" in caplog.text
