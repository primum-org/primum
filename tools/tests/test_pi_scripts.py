"""The scripts that prepare and drive the development Pi, run here without a Pi.

What can be checked off the board: refusing other GPIO software, refusing a board that is not a
Pi, and refusing to run without a host or a pin. The rest runs on the Pi (block 1.4).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="bash scripts")

ROOT = Path(__file__).resolve().parents[2]
CHECK_GPIO_USERS = ROOT / "image" / "check-gpio-users.sh"
PROVISION = ROOT / "image" / "provision.sh"
PI = ROOT / "tools" / "pi.sh"


def _run(script: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 (scripts of this repository)
        ["bash", str(script), *args],  # noqa: S607 (bash from the PATH, as the scripts use it)
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **env},
    )


def _process(proc: Path, pid: int, name: str, *open_files: str) -> None:
    fds = proc / str(pid) / "fd"
    fds.mkdir(parents=True)
    (proc / str(pid) / "comm").write_text(f"{name}\n")
    for number, target in enumerate(open_files):
        (fds / str(number)).symlink_to(target)


def test_check_gpio_users_names_a_process_that_holds_gpiomem(tmp_path: Path) -> None:
    _process(tmp_path, 41, "bash", "/dev/null")
    _process(tmp_path, 42, "python3", "/dev/null", "/dev/gpiomem")

    result = _run(CHECK_GPIO_USERS, PROC=str(tmp_path))

    assert result.returncode == 1
    assert "process 42 (python3) has /dev/gpiomem open" in result.stderr
    assert "41" not in result.stderr


def test_check_gpio_users_passes_when_nothing_drives_gpio(tmp_path: Path) -> None:
    _process(tmp_path, 41, "bash", "/dev/null", "/dev/gpiochip0")

    result = _run(CHECK_GPIO_USERS, PROC=str(tmp_path))

    assert result.returncode == 0, result.stderr


def test_provision_refuses_a_board_that_is_not_a_raspberry_pi(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.write_text("Generic x86 machine\0")

    result = _run(PROVISION, "--app-only", MODEL_FILE=str(model))

    assert result.returncode == 1
    assert "not a Raspberry Pi" in result.stderr


@pytest.mark.parametrize("args", [["--pin"], ["--pin", "seventeen"], ["--force"]])
def test_provision_rejects_invalid_arguments(args: list[str]) -> None:
    result = _run(PROVISION, *args)

    assert result.returncode == 2
    assert "usage:" in result.stderr


def test_pi_tasks_need_a_host_and_have_no_default() -> None:
    env = {key: value for key, value in os.environ.items() if key != "PRIMUM_PI_HOST"}
    result = subprocess.run(  # noqa: S603
        ["bash", str(PI), "sync"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 1
    assert "PRIMUM_PI_HOST" in result.stderr


def test_pi_provision_needs_the_pin_before_touching_the_pi() -> None:
    result = _run(PI, "provision", PRIMUM_PI_HOST="unreachable.invalid")

    assert result.returncode == 1
    assert "provision PIN" in result.stderr
