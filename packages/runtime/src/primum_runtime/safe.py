"""``primum-safe``: put the outputs the runtime declared in their safe state (decision 0020).

systemd runs it after the service stops, whatever stopped it (``ExecStopPost=``). After a
clean stop nothing is declared and it does nothing. After a crash it claims what the dead
service had declared, with the same HAL: a claim starts every output in its safe state, and
closing the HAL reads each one back and releases it. Then it forgets the declaration.

It never guesses: without a declaration it touches nothing, and one it cannot read is an
error. A line someone else holds (the service, still alive) is refused by the HAL.
"""

import argparse
import logging
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from primum_runtime import declared
from primum_runtime.board import load_board
from primum_runtime.config import DEFAULT_DATA_DIR
from primum_runtime.errors import PrimumError
from primum_runtime.hal import Hal, create_hal

log = logging.getLogger(__name__)

EXIT_SAFE = 0
EXIT_FAILED = 1

type OpenHal = Callable[[str], Hal]  # the HAL of a board, by its model


def make_safe(directory: Path, open_hal: OpenHal) -> int:
    """Drive what is declared in ``directory`` to its safe state; the exit status.

    ``EXIT_SAFE`` when nothing was declared, or when every declared output read back safe and
    was released (the declaration is then removed). ``EXIT_FAILED`` otherwise, with the
    declaration kept: the next stop, or the next start of the service, tries again.
    """
    try:
        declaration = declared.read(directory)
        if declaration is None:
            log.info("nothing declared in %s: nothing to make safe", directory)
            return EXIT_SAFE
        pins = declaration.claim().pins()
        with open_hal(declaration.board) as hal:
            hal.claim(declaration.claim())
    except PrimumError as error:
        log.error("the outputs may not be in their safe state: %s", error)
        return EXIT_FAILED
    declared.remove(directory)
    log.info("in their safe state and released: GPIO %s", ", ".join(map(str, pins)) or "none")
    return EXIT_SAFE


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(
        prog="primum-safe",
        description="Put the outputs the Primum runtime declared in their safe state.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("PRIMUM_DATA_DIR", DEFAULT_DATA_DIR)),
        help=f"where the runtime declares what it claims, {DEFAULT_DATA_DIR} by default "
        "(PRIMUM_DATA_DIR)",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    directory: Path = args.data_dir
    return make_safe(directory, lambda model: create_hal(simulate=False, board=load_board(model)))
