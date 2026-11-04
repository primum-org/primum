"""The first-boot script of the image spike (block 1.5), run here on a fake boot partition."""

import getpass
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell script")

FIRSTBOOT = (
    Path(__file__).resolve().parents[2]
    / "image/spike/layer/primum-spike.d/customize.overlay/usr/local/sbin/primum-firstboot"
)


def _firstboot(boot: Path, iwd: Path) -> None:
    subprocess.run(  # noqa: S603 (a script of this repository)
        ["sh", str(FIRSTBOOT), getpass.getuser()],  # noqa: S607
        check=True,
        env={**os.environ, "BOOT_DIR": str(boot), "IWD_DIR": str(iwd)},
    )


def test_wifi_file_from_windows_becomes_an_iwd_profile_and_is_deleted(tmp_path: Path) -> None:
    boot, iwd = tmp_path / "boot", tmp_path / "iwd"
    boot.mkdir()
    (boot / "wifi.txt").write_bytes(b"SSID=Casa_5G\r\nPSK=secret pass\r\n")

    _firstboot(boot, iwd)

    profile = iwd / "Casa_5G.psk"
    assert profile.read_text() == "[Security]\nPassphrase=secret pass\n"
    assert profile.stat().st_mode & 0o777 == 0o600
    assert not (boot / "wifi.txt").exists()


def test_ssid_with_other_characters_gets_iwd_hex_name(tmp_path: Path) -> None:
    boot, iwd = tmp_path / "boot", tmp_path / "iwd"
    boot.mkdir()
    (boot / "wifi.txt").write_text("SSID=Mi red\nPSK=x\n")

    _firstboot(boot, iwd)

    assert (iwd / "=4d6920726564.psk").exists()  # "Mi red" in hex, as iwd names it
