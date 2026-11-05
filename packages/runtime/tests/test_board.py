"""The board profiles the runtime ships, and what the HAL gets from them."""

import json
from pathlib import Path

import pytest

from primum_runtime import board
from primum_runtime.board import available_boards, load_board
from primum_runtime.errors import PrimumError


def test_the_runtime_ships_the_raspberry_pi_4_profile() -> None:
    assert available_boards() == ("rpi4b",)


def test_the_raspberry_pi_4_has_gpios_0_to_27_on_lines_of_the_same_number() -> None:
    rpi4b = load_board("rpi4b")

    assert rpi4b.chip_label == "pinctrl-bcm2711"
    assert rpi4b.lines == {gpio: gpio for gpio in range(28)}


def test_a_pin_the_board_does_not_have_is_invalid() -> None:
    with pytest.raises(PrimumError) as raised:
        load_board("rpi4b").line(28)

    assert raised.value.code == "hal.pin_invalid"
    assert raised.value.params == {"pin": 28, "board": "rpi4b"}


def test_a_broken_profile_is_a_bug_reported_with_its_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = json.loads((board.PROFILES / "rpi4b.json").read_text(encoding="utf-8"))
    profile["reserved"] = [{"gpio": 99, "reason": "hat_eeprom"}]
    (tmp_path / "rpi4b.json").write_text(json.dumps(profile), encoding="utf-8")
    monkeypatch.setattr(board, "PROFILES", tmp_path)

    with pytest.raises(ValueError, match=r"board\.unknown_gpio"):
        load_board("rpi4b")


def test_a_profile_must_be_named_after_its_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "other.json").write_bytes((board.PROFILES / "rpi4b.json").read_bytes())
    monkeypatch.setattr(board, "PROFILES", tmp_path)

    with pytest.raises(ValueError, match="model differs from file name"):
        load_board("other")
