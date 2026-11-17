"""Service configuration, from command-line options or ``PRIMUM_*`` environment variables.

An option given on the command line wins over the environment. Until elements come from a
deployment package (phase 4) the service drives one digital output, named ``led``, and may
listen to one digital input, named ``button``. PWM outputs are not offered here until the
safe-state unit covers their channels (block 3.4): after a ``kill -9`` one would stay at its
last level. The board (``rpi4b`` by default, the only one so far) says which pins exist, on
which GPIO chip, and what it takes for the options of its elements.

The pins have no default on purpose: a default pin is a pin someone may have wired to a relay.
Neither has the pull of the input: every default is wrong for some wiring.
"""

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from primum_core.values import Value
from primum_runtime.board import (
    DEFAULT_BOARD,
    available_boards,
    load_board,
    load_profile,
    option_limits,
)
from primum_runtime.drivers import ElementConfig, OptionLimits
from primum_runtime.hal import BoardGpio, Pull

LED = "led"
BUTTON = "button"
PULLS = tuple(pull.value for pull in Pull)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off", ""})


@dataclass(frozen=True)
class RuntimeConfig:
    simulate: bool
    board: BoardGpio
    limits: OptionLimits
    elements: tuple[ElementConfig, ...]
    host: str
    port: int


def parse_config(argv: Sequence[str], env: Mapping[str, str]) -> RuntimeConfig:
    """Build the configuration from ``argv`` (without the program name) and ``env``.

    Invalid values exit through ``argparse`` with a usage message, as any command-line tool.
    """
    parser = _parser(env)
    args = parser.parse_args(argv)
    pin: int | None = args.pin
    if pin is None:
        parser.error("the pin of the LED is required: --pin or PRIMUM_PIN")
    simulate: bool = args.simulate
    board: str = args.board
    if board not in available_boards():  # argparse checks the choices of options, not defaults
        parser.error(
            f"no profile for board {board!r} (PRIMUM_BOARD): {', '.join(available_boards())}"
        )
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
    host: str = args.host
    port: int = args.port
    return RuntimeConfig(
        simulate=simulate,
        board=load_board(board),
        limits=option_limits(load_profile(board)),
        elements=tuple(elements),
        host=host,
        port=port,
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
        default=env.get("PRIMUM_BOARD", DEFAULT_BOARD),
        help=f"board model, with its pins and GPIO chip; {DEFAULT_BOARD} by default (PRIMUM_BOARD)",
    )
    parser.add_argument(
        "--pin",
        type=int,
        default=_int(env, "PRIMUM_PIN"),
        help="GPIO number of the LED (BCM); required, no default (PRIMUM_PIN)",
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
