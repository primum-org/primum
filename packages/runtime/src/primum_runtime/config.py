"""Service configuration, from command-line options or ``PRIMUM_*`` environment variables.

An option given on the command line wins over the environment. The service is told what
elements it has in one of two ways, never both:

- a deployment package (``--package``): its elements, each by its id, on its board. The
  package is read and checked against the drivers and the board here, before anything is
  claimed, and one that fails is refused whole (``primum_runtime.package``);
- options of its own: one digital output, named ``led`` (``--pin``), and maybe one digital
  input, named ``button``, and one PWM output, named ``dimmer``. They stay until packages
  are activated on the board (block 4.5).

The board (``rpi4b`` by default, the only one so far; a package says its own) says which pins
exist, on which GPIO chip, and what it takes for the options of its elements.

The pins have no default on purpose: a default pin is a pin someone may have wired to a relay.
Neither has the pull of the input: every default is wrong for some wiring.

The service writes in one directory only, ``/data`` unless told otherwise: there it declares
the outputs it claims, so that ``primum-safe`` can make them safe if it dies (decision 0020).
A simulated service has no real outputs and declares nothing.
"""

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from primum_core.generated.model import Package
from primum_core.values import Value
from primum_runtime.board import (
    DEFAULT_BOARD,
    available_boards,
    load_board,
    load_profile,
    option_limits,
)
from primum_runtime.drivers import ElementConfig, OptionLimits, load_manifests
from primum_runtime.hal import BoardGpio, Pull
from primum_runtime.package import load_package, refuse, wiring_problems

LED = "led"
BUTTON = "button"
DIMMER = "dimmer"
PULLS = tuple(pull.value for pull in Pull)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_DATA_DIR = "/data"
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off", ""})


@dataclass(frozen=True)
class RuntimeConfig:
    simulate: bool
    board: BoardGpio
    limits: OptionLimits
    elements: tuple[ElementConfig, ...]
    data_dir: Path
    host: str
    port: int
    package: Package | None = None  # the one the elements come from, if they do
    # Take the system's clock as right without waiting for it to be set from the network:
    # a board with a clock of its own, or a laptop.
    trust_clock: bool = False
    # Told neither a package file nor pins: it runs the package that was activated on it
    # (``primum_runtime.deployed``), and takes others through its API.
    deployed: bool = False
    # The API asks for a paired device (``primum_runtime.pairing``). Off for a laptop and
    # for tests, never on a board: whoever reaches the port commands it.
    pairing: bool = True


def parse_config(argv: Sequence[str], env: Mapping[str, str]) -> RuntimeConfig:
    """Build the configuration from ``argv`` (without the program name) and ``env``.

    Invalid values exit through ``argparse`` with a usage message, as any command-line tool.
    """
    parser = _parser(env)
    args = parser.parse_args(argv)
    package_path: Path | None = args.package
    if package_path is not None:
        return _from_package(package_path, args, parser)
    pin: int | None = args.pin
    simulate: bool = args.simulate
    board: str = args.board or DEFAULT_BOARD
    if board not in available_boards():  # argparse checks the choices of options, not defaults
        parser.error(
            f"no profile for board {board!r} (PRIMUM_BOARD): {', '.join(available_boards())}"
        )
    if pin is None:
        return _deployed(board, args, parser)
    active_low: bool = args.active_low
    elements = [ElementConfig(LED, "digital_output", pin, active_low)]
    input_pin: int | None = args.input_pin
    input_pull: str | None = args.input_pull
    if input_pull is not None and input_pull not in PULLS:  # argparse checks options only
        parser.error(f"PRIMUM_INPUT_PULL must be one of {', '.join(PULLS)}, not {input_pull!r}")
    input_options = (input_pull, args.input_debounce_ms, args.input_active_low or None)
    if input_pin is None and any(option is not None for option in input_options):
        parser.error("options of an input without one: give --input-pin (PRIMUM_INPUT_PIN) too")
    if input_pin is not None:
        if input_pull is None:
            parser.error("the input needs its pull: --input-pull or PRIMUM_INPUT_PULL")
        options: dict[str, Value] = {"pull": input_pull}
        debounce_ms: int | None = args.input_debounce_ms
        if debounce_ms is not None:
            options["debounceMs"] = debounce_ms
        input_active_low: bool = args.input_active_low
        elements.append(
            ElementConfig(BUTTON, "digital_input", input_pin, input_active_low, options)
        )
    pwm_pin: int | None = args.pwm_pin
    pwm_frequency_hz: int | None = args.pwm_frequency_hz
    if pwm_pin is None and pwm_frequency_hz is not None:
        parser.error("a frequency without a PWM output: give --pwm-pin (PRIMUM_PWM_PIN) too")
    if pwm_pin is not None:
        # Without a frequency, its driver's default; whatever it is, its board must take it.
        frequency: dict[str, Value] = {}
        if pwm_frequency_hz is not None:
            frequency["frequencyHz"] = pwm_frequency_hz
        elements.append(ElementConfig(DIMMER, "pwm_output", pwm_pin, False, frequency))
    # Wired as the board allows, by the rules a package's elements are held to: a reserved
    # pin is refused here, since the HAL knows nothing of them.
    refuse(wiring_problems(elements, board))
    host: str = args.host
    port: int = args.port
    return RuntimeConfig(
        simulate=simulate,
        board=load_board(board),
        limits=option_limits(load_profile(board)),
        elements=tuple(elements),
        data_dir=args.data_dir,
        host=host,
        port=port,
        trust_clock=args.trust_clock,
        pairing=not args.no_pairing,
    )


def _deployed(
    board: str, args: argparse.Namespace, parser: argparse.ArgumentParser
) -> RuntimeConfig:
    """The configuration of a service told neither a package file nor a pin: it runs the
    package activated on it, on ``board``, and starts with nothing if there is none."""
    given = _given(args)
    if given:
        parser.error(f"options of elements without --pin (PRIMUM_PIN): remove {given}")
    return RuntimeConfig(
        simulate=args.simulate,
        board=load_board(board),
        limits=option_limits(load_profile(board)),
        elements=(),
        data_dir=args.data_dir,
        host=args.host,
        port=args.port,
        trust_clock=args.trust_clock,
        pairing=not args.no_pairing,
        deployed=True,
    )


def _given(args: argparse.Namespace) -> str:
    """The options of elements that were given, as they are written; none: empty."""
    # By identity: 0 is a pin and a debounce like any other, and in Python it equals False.
    values = {name: getattr(args, name) for name in _ELEMENT_OPTIONS}
    given = [name for name, value in values.items() if value is not None and value is not False]
    return ", ".join("--" + name.replace("_", "-") for name in given)


# The options that say what elements there are: with a package, the package says it.
_ELEMENT_OPTIONS = (
    "pin",
    "active_low",
    "input_pin",
    "input_pull",
    "input_active_low",
    "input_debounce_ms",
    "pwm_pin",
    "pwm_frequency_hz",
)


def _from_package(
    path: Path, args: argparse.Namespace, parser: argparse.ArgumentParser
) -> RuntimeConfig:
    """The configuration of a service that runs a package: its board and its elements are
    the package's. Raises what ``load_package`` does for one it cannot run."""
    given = _given(args)
    if given:
        parser.error(f"a package says what elements there are: remove {given} (or PRIMUM_*)")
    loaded = load_package(path, load_manifests())
    model = loaded.package.board.model
    board: str | None = args.board
    if board is not None and board != model:
        parser.error(f"the package is for a board {model!r}, not {board!r} (PRIMUM_BOARD)")
    simulate: bool = args.simulate
    host: str = args.host
    port: int = args.port
    return RuntimeConfig(
        simulate=simulate,
        board=load_board(model),
        limits=option_limits(load_profile(model)),
        elements=loaded.elements,
        data_dir=args.data_dir,
        host=host,
        port=port,
        package=loaded.package,
        trust_clock=args.trust_clock,
        pairing=not args.no_pairing,
    )


def _parser(env: Mapping[str, str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="primum-runtime", description="Primum runtime: local API for the outputs."
    )
    parser.add_argument(
        "--simulate",
        action=argparse.BooleanOptionalAction,
        default=_flag(env, "PRIMUM_SIMULATE"),
        help="use the simulated HAL instead of the GPIO chip (PRIMUM_SIMULATE)",
    )
    parser.add_argument(
        "--board",
        choices=available_boards(),
        default=env.get("PRIMUM_BOARD") or None,
        help=f"board model, with its pins and GPIO chip; {DEFAULT_BOARD} by default, or the "
        "one of the package (PRIMUM_BOARD)",
    )
    parser.add_argument(
        "--package",
        type=Path,
        default=Path(env["PRIMUM_PACKAGE"]) if env.get("PRIMUM_PACKAGE") else None,
        help="the deployment package to run (built by `primum build`): its elements and its "
        "board; instead of --pin and the other options of elements (PRIMUM_PACKAGE)",
    )
    parser.add_argument(
        "--pin",
        type=int,
        default=_int(env, "PRIMUM_PIN"),
        help="GPIO number of the LED (BCM); required without a package, no default (PRIMUM_PIN)",
    )
    parser.add_argument(
        "--active-low",
        action=argparse.BooleanOptionalAction,
        default=_flag(env, "PRIMUM_ACTIVE_LOW"),
        help="the LED is on when the line is low (PRIMUM_ACTIVE_LOW)",
    )
    parser.add_argument(
        "--input-pin",
        type=int,
        default=_int(env, "PRIMUM_INPUT_PIN"),
        help="GPIO number of an input to listen to (a button); none by default (PRIMUM_INPUT_PIN)",
    )
    parser.add_argument(
        "--input-pull",
        choices=PULLS,
        default=env.get("PRIMUM_INPUT_PULL") or None,  # empty in an env file: not given
        help="the pull of the input: up for a button to ground, down for one to 3V3, none for "
        "a sensor that drives the line; required with the input, no default (PRIMUM_INPUT_PULL)",
    )
    parser.add_argument(
        "--input-active-low",
        action=argparse.BooleanOptionalAction,
        default=_flag(env, "PRIMUM_INPUT_ACTIVE_LOW"),
        help="the input is active when the line is low, as a button to ground "
        "(PRIMUM_INPUT_ACTIVE_LOW)",
    )
    parser.add_argument(
        "--input-debounce-ms",
        type=int,
        default=_int(env, "PRIMUM_INPUT_DEBOUNCE_MS"),
        help="ignore bounces of the input shorter than this; its driver's default if not given "
        "(PRIMUM_INPUT_DEBOUNCE_MS)",
    )
    parser.add_argument(
        "--pwm-pin",
        type=int,
        default=_int(env, "PRIMUM_PWM_PIN"),
        help="GPIO number of a PWM output (a dimmed LED), one with hardware PWM; none by "
        "default (PRIMUM_PWM_PIN)",
    )
    parser.add_argument(
        "--pwm-frequency-hz",
        type=int,
        default=_int(env, "PRIMUM_PWM_FREQUENCY_HZ"),
        help="frequency of the PWM output; its driver's default if not given "
        "(PRIMUM_PWM_FREQUENCY_HZ)",
    )
    parser.add_argument(
        "--trust-clock",
        action=argparse.BooleanOptionalAction,
        default=_flag(env, "PRIMUM_TRUST_CLOCK"),
        help="take the system's time as right without waiting for it to be set from the "
        "network: for a board with a clock of its own (PRIMUM_TRUST_CLOCK=1)",
    )
    parser.add_argument(
        "--no-pairing",
        action="store_true",
        default=_flag(env, "PRIMUM_NO_PAIRING"),
        help="let anyone who reaches the service use it, without the pairing code: for a "
        "laptop, never for a board (PRIMUM_NO_PAIRING=1)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(env.get("PRIMUM_DATA_DIR", DEFAULT_DATA_DIR)),
        help="the only directory the service writes: there it declares the outputs it claims, "
        f"for primum-safe; {DEFAULT_DATA_DIR} by default (PRIMUM_DATA_DIR)",
    )
    parser.add_argument(
        "--host",
        default=env.get("PRIMUM_HOST", DEFAULT_HOST),
        help=f"address to listen on, {DEFAULT_HOST} by default (PRIMUM_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_int(env, "PRIMUM_PORT", DEFAULT_PORT),
        help=f"port to listen on, {DEFAULT_PORT} by default (PRIMUM_PORT)",
    )
    return parser


def _flag(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name, "").strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise SystemExit(f"{name} must be true or false, not {value!r}")


def _int(env: Mapping[str, str], name: str, default: int | None = None) -> int | None:
    value = env.get(name)
    if value is None:
        return default
    if not value.strip().isdecimal():
        raise SystemExit(f"{name} must be a number, not {value!r}")
    return int(value)
