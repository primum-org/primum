"""Hardware PWM through the kernel's sysfs interface (``/sys/class/pwm``).

A board profile names the PWM controller by its device (``fe20c000.pwm`` on a Raspberry Pi 4),
because its chip number can change with the kernel. Each channel is a directory with ``period``
and ``duty_cycle`` in nanoseconds and an ``enable`` flag. On a Raspberry Pi the controller only
exists once the ``pwm`` overlay is enabled in ``config.txt`` (the hardware manager's job from
phase 6; until then ``image/provision.sh`` enables it on the development Pi).

A freshly exported channel belongs to root until udev hands it to the ``gpio`` group (Raspberry
Pi OS does so some 10 ms after the export), so the HAL waits for it to become writable.
"""

import errno
import os
from collections.abc import Callable
from pathlib import Path
from time import sleep

from primum_runtime.errors import ErrorCode, PrimumError

SYSFS_PWM = Path("/sys/class/pwm")
NS_PER_S = 1_000_000_000
EXPORT_SETTLE_ATTEMPTS = 100
EXPORT_SETTLE_STEP_S = 0.01
CHANNEL_FILES = ("enable", "duty_cycle", "period")


class SysfsPwmChannel:
    """One exported channel, enabled at 0 %.

    ``wait`` pauses for a number of seconds while udev settles after an export; tests inject
    their own.
    """

    def __init__(
        self,
        chip: Path,
        channel: int,
        pin: int,
        frequency_hz: int,
        wait: Callable[[float], None] = sleep,
    ) -> None:
        self._chip = chip
        self._channel = channel
        self._pin = pin
        self._path = chip / f"pwm{channel}"
        self._period_ns = NS_PER_S // frequency_hz
        try:
            if not self._path.exists():
                _write(chip / "export", channel)
                _wait_until_writable(self._path, wait)
            _write(self._path / "enable", 0)
            # Duty cycle first: the kernel refuses a period shorter than the duty cycle a
            # channel adopted after a crash still holds.
            _write(self._path / "duty_cycle", 0)
            _write(self._path / "period", self._period_ns)
            _write(self._path / "enable", 1)
        except OSError as error:
            raise self._unavailable(error) from error

    def write(self, duty: float) -> None:
        try:
            _write(self._path / "duty_cycle", round(duty * self._period_ns))
        except OSError as error:
            raise self._unavailable(error) from error

    def read(self) -> float:
        try:
            return int((self._path / "duty_cycle").read_text()) / self._period_ns
        except OSError as error:
            raise self._unavailable(error) from error

    def release(self) -> None:
        """Leave the channel at 0 %, disabled and unexported."""
        try:
            _write(self._path / "duty_cycle", 0)
            _write(self._path / "enable", 0)
            _write(self._chip / "unexport", self._channel)
        except OSError as error:
            raise self._unavailable(error) from error

    def _unavailable(self, error: OSError) -> PrimumError:
        params = {"pin": self._pin, "channel": self._channel, "detail": _detail(error)}
        return PrimumError(ErrorCode.HAL_PWM_UNAVAILABLE, params)


def find_pwm_chip(device: str, sysfs: Path = SYSFS_PWM) -> Path:
    """The ``pwmchipN`` directory whose device is ``device``; ``hal.pwm_chip_not_found``."""
    found: list[str] = []
    for chip in sorted(sysfs.glob("pwmchip*")):
        try:
            name = (chip / "device").resolve().name
        except OSError as error:
            found.append(f"{chip.name}: {_detail(error)}")
            continue
        if name == device:
            return chip
        found.append(f"{chip.name} ({name})")
    detail = f"found {', '.join(found)}" if found else "no PWM controller found"
    raise PrimumError(ErrorCode.HAL_PWM_CHIP_NOT_FOUND, {"device": device, "detail": detail})


def _wait_until_writable(channel: Path, wait: Callable[[float], None]) -> None:
    """Wait, briefly, for udev to make the channel's files writable (it goes file by file);
    ``PermissionError`` if they never are."""
    for _ in range(EXPORT_SETTLE_ATTEMPTS):
        if all(os.access(channel / name, os.W_OK) for name in CHANNEL_FILES):
            return
        wait(EXPORT_SETTLE_STEP_S)
    raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), str(channel))


def _write(path: Path, value: int) -> None:
    path.write_text(f"{value}\n")


def _detail(error: OSError) -> str:
    return error.strerror or str(error)
