"""Hardware PWM through sysfs, against a fake /sys/class/pwm tree in a temporary folder."""

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


def _export(chip: Path) -> None:
    """What the kernel does when a channel number is written to ``export``: creates pwmN."""
    channel = int((chip / "export").read_text())
    directory = chip / f"pwm{channel}"
    directory.mkdir()
    for name in ("period", "duty_cycle", "enable"):
        (directory / name).write_text("0\n")


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
    write = pwm_sysfs._write  # pyright: ignore[reportPrivateUsage] -- wrapped to play the kernel

    def write_and_act_as_the_kernel(path: Path, value: int) -> None:
        write(path, value)
        if path.name == "export":  # the kernel creates pwmN when N is written to export
            _export(path.parent)

    monkeypatch.setattr(pwm_sysfs, "_write", write_and_act_as_the_kernel)

    channel = SysfsPwmChannel(chip, 1, pin=19, frequency_hz=25_000)

    assert (chip / "pwm1" / "period").read_text() == "40000\n"
    assert (chip / "pwm1" / "duty_cycle").read_text() == "0\n"
    assert (chip / "pwm1" / "enable").read_text() == "1\n"
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
