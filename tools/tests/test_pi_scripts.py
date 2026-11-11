"""The scripts that prepare and drive the development Pi, run here without a Pi.

What can be checked off the board: refusing other GPIO software, refusing a board that is not a
Pi, the host the Pi tasks use and refusing to provision without a pin. The rest was checked on
the development Pi (block 1.4).
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


@pytest.mark.skipif(os.geteuid() == 0, reason="checks what happens without root")
def test_check_gpio_users_refuses_to_run_without_root() -> None:
    env = {key: value for key, value in os.environ.items() if key != "PROC"}
    result = subprocess.run(  # noqa: S603
        ["bash", str(CHECK_GPIO_USERS)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    # Without root other users' processes are invisible: passing would be a false "all clear".
    assert result.returncode == 2
    assert "run it as root" in result.stderr


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


def _fake_rsync(directory: Path) -> str:
    """A PATH whose rsync prints its arguments and fails, so nothing reaches a real host."""
    rsync = directory / "rsync"
    rsync.write_text('#!/bin/sh\necho "rsync $*" >&2\nexit 1\n')
    rsync.chmod(0o755)
    return f"{directory}{os.pathsep}{os.environ['PATH']}"


def test_pi_tasks_use_primum_dev_when_no_host_is_set(tmp_path: Path) -> None:
    env = {key: value for key, value in os.environ.items() if key != "PRIMUM_PI_HOST"}
    env["PATH"] = _fake_rsync(tmp_path)
    result = subprocess.run(  # noqa: S603
        ["bash", str(PI), "sync"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 1
    assert "primum-dev:primum-src/" in result.stderr


def test_pi_tasks_use_the_host_in_primum_pi_host(tmp_path: Path) -> None:
    result = _run(PI, "sync", PRIMUM_PI_HOST="other-pi", PATH=_fake_rsync(tmp_path))

    assert "other-pi:primum-src/" in result.stderr


def _fake_pi(directory: Path) -> str:
    """A PATH whose rsync does nothing and whose ssh prints its command line instead of
    running it on a Pi."""
    (directory / "rsync").write_text("#!/bin/sh\nexit 0\n")
    (directory / "ssh").write_text('#!/bin/sh\necho "ssh $*" >&2\ncat >/dev/null\n')
    for name in ("rsync", "ssh"):
        (directory / name).chmod(0o755)
    return f"{directory}{os.pathsep}{os.environ['PATH']}"


def _run_without_pins(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
    """Run pi.sh with the optional pins of the shell they run in forgotten."""
    clean = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PRIMUM_HW_INPUT_PIN", "PRIMUM_HW_PWM_PIN")
    }
    return subprocess.run(  # noqa: S603
        ["bash", str(PI), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        env={**clean, **env},
    )


def test_pi_test_forwards_only_the_optional_pins_that_are_set(tmp_path: Path) -> None:
    result = _run_without_pins("test", PRIMUM_HW_PWM_PIN="18", PATH=_fake_pi(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "ssh primum-dev env PRIMUM_HW_PWM_PIN=18 bash -s -- primum-src" in result.stderr


def test_pi_test_runs_with_no_optional_pin_at_all(tmp_path: Path) -> None:
    result = _run_without_pins("test", PATH=_fake_pi(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "ssh primum-dev env bash -s -- primum-src" in result.stderr


def test_pi_provision_needs_the_pin_before_touching_the_pi() -> None:
    result = _run(PI, "provision", PRIMUM_PI_HOST="unreachable.invalid")

    assert result.returncode == 1
    assert "provision PIN" in result.stderr
