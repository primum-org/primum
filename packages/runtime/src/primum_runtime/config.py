"""Service configuration, from command-line options or ``PRIMUM_*`` environment variables.

An option given on the command line wins over the environment. Phase 1 drives one output,
named ``led``; later, outputs come from the deployment package. The board (``rpi4b`` by
default, the only one so far) says which pins exist and on which GPIO chip.

The pin has no default on purpose: a default pin is a pin someone may have wired to a relay.
"""

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from primum_runtime.board import DEFAULT_BOARD, available_boards, load_board
from primum_runtime.hal import BoardGpio, OutputSpec

LED = "led"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off", ""})


@dataclass(frozen=True)
class RuntimeConfig:
    simulate: bool
    board: BoardGpio
    outputs: Mapping[str, OutputSpec]
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
    host: str = args.host
    port: int = args.port
    return RuntimeConfig(
        simulate=simulate,
        board=load_board(board),
        outputs={LED: OutputSpec(pin=pin, active_low=active_low)},
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
