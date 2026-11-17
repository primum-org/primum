"""The board the runtime drives, from its board profile.

The profiles of ``boards/`` are copied into the package (``primum_runtime/generated/boards/``,
by ``just gen``), so the installed runtime has them. ``core`` reads and checks a profile; the
HAL gets what it needs from it: the GPIO chip's label, the line of each GPIO and the
frequencies its PWM takes. The drivers get the limits it puts on the options of its elements.
"""

from pathlib import Path, PurePosixPath

from primum_core.boards import gpio_lines
from primum_core.formats import read_board_profile
from primum_core.generated.model import BoardProfile
from primum_runtime.drivers import OptionLimits
from primum_runtime.hal import PWM_FREQUENCY_HZ, BoardGpio

PROFILES = Path(__file__).resolve().parent / "generated" / "boards"
DEFAULT_BOARD = "rpi4b"
# The limit of a profile that the HAL enforces too: the frequency of its PWM.
PWM_FREQUENCY = ("pwm_output", "frequencyHz")


def available_boards() -> tuple[str, ...]:
    """The models with a profile, by name (``rpi4b``)."""
    return tuple(sorted(path.stem for path in PROFILES.glob("*.json")))


def load_profile(model: str) -> BoardProfile:
    """The profile of ``model``.

    A profile ships with Primum and is checked by its tests, so a broken one is a bug: it
    raises ``ValueError`` with the issues instead of a user-facing error.
    """
    path = PROFILES / f"{model}.json"
    parsed = read_board_profile(PurePosixPath(path.name), path.read_bytes())
    profile = parsed.value
    if profile is None or profile.model != model:
        codes = ", ".join(issue.code for issue in parsed.issues) or "model differs from file name"
        raise ValueError(f"invalid board profile {path}: {codes}")
    return profile


def option_limits(profile: BoardProfile) -> OptionLimits:
    """The limits the board puts on the options of its elements, as the drivers take them."""
    return {(limit.element_type, limit.option): (limit.min, limit.max) for limit in profile.limits}


def load_board(model: str) -> BoardGpio:
    """The GPIOs of ``model``, from its profile."""
    profile = load_profile(model)
    lowest, highest = option_limits(profile).get(PWM_FREQUENCY, PWM_FREQUENCY_HZ)
    return BoardGpio(
        model=model,
        chip_label=profile.gpio_chip.label,
        lines=gpio_lines(profile),
        pwm_device=profile.pwm_chip.device,
        pwm_channels={
            gpio: channel.channel for channel in profile.pwm_channels for gpio in channel.gpios
        },
        pwm_frequency_hz=(int(lowest), int(highest)),
    )
