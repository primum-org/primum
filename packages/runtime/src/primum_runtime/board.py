"""The board the runtime drives, from its board profile.

The profiles of ``boards/`` are copied into the package (``primum_runtime/generated/boards/``,
by ``just gen``), so the installed runtime has them. ``core`` reads and checks a profile; the
HAL gets what it needs from it: the GPIO chip's label and the line of each GPIO.
"""

from pathlib import Path, PurePosixPath

from primum_core.boards import gpio_lines
from primum_core.formats import read_board_profile
from primum_runtime.hal import BoardGpio

PROFILES = Path(__file__).resolve().parent / "generated" / "boards"
DEFAULT_BOARD = "rpi4b"


def available_boards() -> tuple[str, ...]:
    """The models with a profile, by name (``rpi4b``)."""
    return tuple(sorted(path.stem for path in PROFILES.glob("*.json")))


def load_board(model: str) -> BoardGpio:
    """The GPIOs of ``model``, from its profile.

    A profile ships with Primum and is checked by its tests, so a broken one is a bug: it
    raises ``ValueError`` with the issues instead of a user-facing error.
    """
    path = PROFILES / f"{model}.json"
    parsed = read_board_profile(PurePosixPath(path.name), path.read_bytes())
    profile = parsed.value
    if profile is None or profile.model != model:
        codes = ", ".join(issue.code for issue in parsed.issues) or "model differs from file name"
        raise ValueError(f"invalid board profile {path}: {codes}")
    return BoardGpio(model=model, chip_label=profile.gpio_chip.label, lines=gpio_lines(profile))
