from pathlib import Path

import pytest

from gen_ui_assets import Source, differences, expected, write


@pytest.fixture
def sources(tmp_path: Path) -> tuple[Source, ...]:
    i18n = tmp_path / "i18n"
    i18n.mkdir()
    (i18n / "en.json").write_text("{}")
    (i18n / "README.md").write_text("not copied")
    return (Source(i18n, "*.json", "i18n"),)


def test_write_copies_matching_files_and_check_then_finds_nothing(
    sources: tuple[Source, ...], tmp_path: Path
) -> None:
    target = tmp_path / "generated"
    files = expected(sources, target)

    write(files, target)

    assert (target / "i18n" / "en.json").read_text() == "{}"
    assert not (target / "i18n" / "README.md").exists()
    assert differences(files, target) == []


def test_check_reports_stale_and_extra_copies(sources: tuple[Source, ...], tmp_path: Path) -> None:
    target = tmp_path / "generated"
    files = expected(sources, target)
    write(files, target)
    (target / "i18n" / "en.json").write_text('{"edited": true}')
    (target / "i18n" / "old.json").write_text("{}")

    assert differences(files, target) == [
        "extra: i18n/old.json",
        "missing or stale: i18n/en.json",
    ]


def test_write_removes_copies_whose_source_is_gone(
    sources: tuple[Source, ...], tmp_path: Path
) -> None:
    target = tmp_path / "generated"
    (target / "i18n").mkdir(parents=True)
    (target / "i18n" / "old.json").write_text("{}")

    write(expected(sources, target), target)

    assert not (target / "i18n" / "old.json").exists()
