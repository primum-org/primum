"""Hardware PWM through sysfs, against a fake /sys/class/pwm tree in a temporary folder."""

import errno
import os
import stat
from collections.abc import Callable
from pathlib import Path

import pytest

from primum_runtime.errors import PrimumError
from primum_runtime.hal import pwm_sysfs
from primum_runtime.hal.pwm_sysfs import SysfsPwmChannel, find_pwm_chip

DEVICE = "fe20c000.pwm"


def _chip(sysfs: Path, name: str, device: str, channels: int = 2) -> Path:
    """A pwmchip directory as the kernel lays it out: a device link, export and unexport."""
    chip = sysfs / name
    chip.mkdir(parents=True)
    target = sysfs / "devices" / device
    target.mkdir(parents=True)
    (chip / "device").symlink_to(target)
    (chip / "npwm").write_text(f"{channels}\n")
    (chip / "export").write_text("")
    (chip / "unexport").write_text("")
    return chip


# A freshly exported channel on the Pi's kernel: 1 ms period, 0 duty cycle, disabled. The
# HAL counts on the period being non-zero (see pwm_sysfs.py).
FRESH_CHANNEL: dict[str, int | str] = {
    "period": 1_000_000,
    "duty_cycle": 0,
    "enable": 0,
    "polarity": "normal",
}


def _export(chip: Path) -> None:
    """What the kernel does when a channel number is written to ``export``: creates pwmN."""
    channel = int((chip / "export").read_text())
    directory = chip / f"pwm{channel}"
    directory.mkdir()
    for name, value in FRESH_CHANNEL.items():
        (directory / name).write_text(f"{value}\n")


def _export_owned_by_root(chip: Path) -> None:
    """An export as udev has not settled yet: the channel's files are not writable."""
    _export(chip)
    channel = int((chip / "export").read_text())
    for name in FRESH_CHANNEL:
        (chip / f"pwm{channel}" / name).chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def _settle(chip: Path, channel: int) -> None:
    """What udev does a little after the export: hands the channel's files to the user."""
    for name in FRESH_CHANNEL:
        (chip / f"pwm{channel}" / name).chmod(stat.S_IRUSR | stat.S_IWUSR)


def _write_and_act_as_the_kernel(
    monkeypatch: pytest.MonkeyPatch, export: Callable[[Path], None]
) -> None:
    """Make every write of the HAL reach the fake tree, and ``export`` create ``pwmN``."""
    write = pwm_sysfs._write  # pyright: ignore[reportPrivateUsage] -- wrapped to play the kernel

    def write_and_act(path: Path, value: int) -> None:
        write(path, value)
        if path.name == "export":
            export(path.parent)

    monkeypatch.setattr(pwm_sysfs, "_write", write_and_act)


not_as_root = pytest.mark.skipif(os.geteuid() == 0, reason="root may write anything")


@pytest.fixture
def sysfs(tmp_path: Path) -> Path:
    _chip(tmp_path, "pwmchip0", "other.pwm")
    _chip(tmp_path, "pwmchip2", DEVICE)
    return tmp_path


def test_the_controller_is_found_by_its_device(sysfs: Path) -> None:
    assert find_pwm_chip(DEVICE, sysfs) == sysfs / "pwmchip2"


def test_a_missing_controller_names_the_ones_found(sysfs: Path) -> None:
    with pytest.raises(PrimumError) as raised:
        find_pwm_chip("missing.pwm", sysfs)

    assert raised.value.code == "hal.pwm_chip_not_found"
    assert raised.value.params == {
        "device": "missing.pwm",
        "detail": "found pwmchip0 (other.pwm), pwmchip2 (fe20c000.pwm)",
    }


def test_no_controller_at_all(tmp_path: Path) -> None:
    with pytest.raises(PrimumError) as raised:
        find_pwm_chip(DEVICE, tmp_path)

    assert raised.value.params == {"device": DEVICE, "detail": "no PWM controller found"}


def test_a_channel_is_exported_set_to_its_period_and_enabled_at_zero(
    sysfs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chip = sysfs / "pwmchip2"
    _write_and_act_as_the_kernel(monkeypatch, _export)

    channel = SysfsPwmChannel(chip, 1, pin=19, frequency_hz=25_000)

    assert (chip / "pwm1" / "period").read_text() == "40000\n"
    assert (chip / "pwm1" / "duty_cycle").read_text() == "0\n"
    assert (chip / "pwm1" / "enable").read_text() == "1\n"
    assert channel.read() == 0.0


@not_as_root
def test_a_fresh_export_is_waited_for_until_udev_makes_it_writable(
    sysfs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chip = sysfs / "pwmchip2"
    _write_and_act_as_the_kernel(monkeypatch, _export_owned_by_root)
    waits: list[float] = []

    def wait_as_udev_settles(seconds: float) -> None:
        waits.append(seconds)
        if len(waits) == 2:
            _settle(chip, 0)

    channel = SysfsPwmChannel(chip, 0, pin=18, frequency_hz=1000, wait=wait_as_udev_settles)

    assert waits == [pwm_sysfs.EXPORT_SETTLE_STEP_S] * 2
    assert (chip / "pwm0" / "enable").read_text() == "1\n"
    assert channel.read() == 0.0


@not_as_root
def test_a_channel_udev_never_hands_over_is_unavailable(
    sysfs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chip = sysfs / "pwmchip2"
    _write_and_act_as_the_kernel(monkeypatch, _export_owned_by_root)
    waits: list[float] = []

    with pytest.raises(PrimumError) as raised:
        SysfsPwmChannel(chip, 0, pin=18, frequency_hz=1000, wait=waits.append)

    assert raised.value.code == "hal.pwm_unavailable"
    assert raised.value.params["detail"] == "Permission denied"
    assert len(waits) == pwm_sysfs.EXPORT_SETTLE_ATTEMPTS


@not_as_root
def test_every_file_of_the_channel_is_waited_for_not_only_enable(
    sysfs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chip = sysfs / "pwmchip2"

    def export_with_enable_handed_over_first(chip: Path) -> None:
        _export_owned_by_root(chip)  # udev goes file by file: enable is writable, the rest not
        (chip / "pwm0" / "enable").chmod(stat.S_IRUSR | stat.S_IWUSR)

    _write_and_act_as_the_kernel(monkeypatch, export_with_enable_handed_over_first)
    waits: list[float] = []

    def wait_as_udev_settles(seconds: float) -> None:
        waits.append(seconds)
        _settle(chip, 0)

    channel = SysfsPwmChannel(chip, 0, pin=18, frequency_hz=1000, wait=wait_as_udev_settles)

    assert waits == [pwm_sysfs.EXPORT_SETTLE_STEP_S]
    assert channel.read() == 0.0


def test_a_channel_adopted_with_a_long_duty_cycle_is_zeroed_before_its_period_shrinks(
    sysfs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Left by a crash: exported, 1 kHz, 50 %. The kernel refuses a period shorter than the duty
    # cycle, so the order of the writes matters.
    chip = sysfs / "pwmchip2"
    (chip / "export").write_text("0")
    _export(chip)
    (chip / "pwm0" / "period").write_text("1000000\n")
    (chip / "pwm0" / "duty_cycle").write_text("500000\n")
    (chip / "pwm0" / "enable").write_text("1\n")
    write = pwm_sysfs._write  # pyright: ignore[reportPrivateUsage] -- wrapped to play the kernel

    def write_as_the_kernel_checks(path: Path, value: int) -> None:
        if path.name == "period" and value < int((path.parent / "duty_cycle").read_text()):
            raise OSError(errno.EINVAL, "Invalid argument")
        write(path, value)

    monkeypatch.setattr(pwm_sysfs, "_write", write_as_the_kernel_checks)

    channel = SysfsPwmChannel(chip, 0, pin=18, frequency_hz=10_000)

    assert (chip / "pwm0" / "period").read_text() == "100000\n"
    assert (chip / "pwm0" / "duty_cycle").read_text() == "0\n"
    assert channel.read() == 0.0


def test_a_channel_adopted_with_inversed_polarity_is_set_to_normal_while_disabled(
    sysfs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Inversed, 0 % holds the pin high; the polarity outlives an unexport and the kernel only
    # lets it change while the channel is disabled.
    chip = sysfs / "pwmchip2"
    (chip / "export").write_text("0")
    _export(chip)
    (chip / "pwm0" / "polarity").write_text("inversed\n")
    (chip / "pwm0" / "enable").write_text("1\n")
    write = pwm_sysfs._write  # pyright: ignore[reportPrivateUsage] -- wrapped to play the kernel

    def write_as_the_kernel_checks(path: Path, value: int | str) -> None:
        if path.name == "polarity" and (path.parent / "enable").read_text() == "1\n":
            raise OSError(errno.EBUSY, "Device or resource busy")
        write(path, value)

    monkeypatch.setattr(pwm_sysfs, "_write", write_as_the_kernel_checks)

    channel = SysfsPwmChannel(chip, 0, pin=18, frequency_hz=1000)

    assert (chip / "pwm0" / "polarity").read_text() == "normal\n"
    assert (chip / "pwm0" / "enable").read_text() == "1\n"
    assert channel.read() == 0.0


def test_a_polarity_inverted_behind_the_hal_reads_as_the_level_the_pin_gets(sysfs: Path) -> None:
    chip = sysfs / "pwmchip2"
    (chip / "export").write_text("0")
    _export(chip)
    channel = SysfsPwmChannel(chip, 0, pin=18, frequency_hz=1000)
    (chip / "pwm0" / "polarity").write_text("inversed\n")  # another program, after the claim

    channel.write(0.0)

    assert channel.read() == 1.0  # 0 % inversed is a pin held high: not the safe state


def test_a_channel_already_exported_is_not_waited_for(sysfs: Path) -> None:
    chip = sysfs / "pwmchip2"
    (chip / "export").write_text("0")
    _export(chip)

    def never(seconds: float) -> None:
        pytest.fail("nothing to wait for: the channel was already exported")

    channel = SysfsPwmChannel(chip, 0, pin=18, frequency_hz=1000, wait=never)

    assert channel.read() == 0.0


def test_a_level_becomes_a_duty_cycle_in_nanoseconds_and_reads_back(sysfs: Path) -> None:
    chip = sysfs / "pwmchip2"
    (chip / "export").write_text("0")
    _export(chip)
    channel = SysfsPwmChannel(chip, 0, pin=18, frequency_hz=1000)

    channel.write(0.25)

    assert (chip / "pwm0" / "duty_cycle").read_text() == "250000\n"
    assert channel.read() == 0.25


def test_release_leaves_the_channel_at_zero_disabled_and_unexported(sysfs: Path) -> None:
    chip = sysfs / "pwmchip2"
    (chip / "export").write_text("0")
    _export(chip)
    channel = SysfsPwmChannel(chip, 0, pin=18, frequency_hz=1000)
    channel.write(0.5)

    channel.release()

    assert (chip / "pwm0" / "duty_cycle").read_text() == "0\n"
    assert (chip / "pwm0" / "enable").read_text() == "0\n"
    assert (chip / "unexport").read_text() == "0\n"


def test_a_channel_that_cannot_be_written_is_unavailable(sysfs: Path) -> None:
    chip = sysfs / "pwmchip2"
    (chip / "export").write_text("0")
    _export(chip)
    channel = SysfsPwmChannel(chip, 0, pin=18, frequency_hz=1000)
    (chip / "pwm0" / "duty_cycle").unlink()
    (chip / "pwm0" / "duty_cycle").mkdir()  # writing to a directory fails as the kernel would

    with pytest.raises(PrimumError) as raised:
        channel.write(0.5)

    assert raised.value.code == "hal.pwm_unavailable"
    assert raised.value.params["pin"] == 18
    assert raised.value.params["channel"] == 0
