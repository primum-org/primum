"""``primum-pairing``: show the board's pairing code, or renew it.

Run on the board, as root or as the user of the service (the code is theirs alone to
read). ``--renew`` makes a new code and forgets every paired device: for a board that
changes hands, or a device that was lost with nobody left to forget it from.
"""

import argparse
import logging
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from primum_runtime.config import DEFAULT_DATA_DIR
from primum_runtime.errors import PrimumError
from primum_runtime.pairing import Pairing

log = logging.getLogger(__name__)

EXIT_FAILED = 1


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(
        prog="primum-pairing", description="Show the pairing code of this board, or renew it."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("PRIMUM_DATA_DIR", DEFAULT_DATA_DIR)),
        help=f"the service's data directory; {DEFAULT_DATA_DIR} by default (PRIMUM_DATA_DIR)",
    )
    parser.add_argument(
        "--renew",
        action="store_true",
        help="make a new code and forget every paired device",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    pairing = Pairing(args.data_dir, time.monotonic)
    try:
        code = pairing.renew() if args.renew else pairing.code()
    except PrimumError as error:
        log.error("the pairing code cannot be kept: %s", error)
        return EXIT_FAILED
    sys.stdout.write(code + "\n")
    return 0
