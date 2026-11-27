"""The ``.primum`` file: a project as one zip, written the same every time and read with care."""

import random
import stat
import struct
import unicodedata
import zipfile
from io import BytesIO
from pathlib import PurePosixPath

import pytest

from primum_core import archive
from primum_core.archive import read_archive, write_archive
from primum_core.errors import CoreErrorCode

FILES = {
    PurePosixPath("project.json"): b'{"name": "Shop"}',
    PurePosixPath("scenes/blink.sec"): b"{}",
    PurePosixPath("Se\u00f1al/luz.vars"): b"{}",
}


def _zip(entries: dict[str, bytes]) -> bytes:
    content = BytesIO()
    with zipfile.ZipFile(content, "w") as packed:
        for name, data in entries.items():
            packed.writestr(zipfile.ZipInfo(name), data)
    return content.getvalue()


def _archive(files: dict[PurePosixPath, bytes]) -> bytes:
    written = write_archive(files)
    assert written.value is not None, written.issues
    return written.value


def _refusal(content: bytes) -> tuple[CoreErrorCode, dict[str, object]]:
    parsed = read_archive(content)
    assert parsed.value is None
    (issue,) = parsed.issues
    assert issue.location is None
    return issue.code, dict(issue.params)


def test_an_archive_read_back_gives_the_files_it_was_written_from() -> None:
    assert read_archive(_archive(FILES)).value == FILES


def test_an_archive_is_the_same_bytes_whatever_order_its_files_are_given_in() -> None:
    backwards = dict(reversed(FILES.items()))

    assert _archive(backwards) == _archive(FILES)


def test_an_archive_is_written_with_no_date_of_its_own_and_as_plain_files() -> None:
    with zipfile.ZipFile(BytesIO(_archive(FILES))) as packed:
        entries = packed.infolist()

    assert {entry.date_time for entry in entries} == {(1980, 1, 1, 0, 0, 0)}
    assert all(stat.S_ISREG(entry.external_attr >> 16) for entry in entries)
    assert {entry.create_system for entry in entries} == {3}


def test_an_archive_made_by_another_program_is_read_and_its_folders_skipped() -> None:
    content = _zip({"project.json": b"{}", "scenes/": b"", "scenes/a.sec": b"1"})

    assert read_archive(content).value == {
        PurePosixPath("project.json"): b"{}",
        PurePosixPath("scenes/a.sec"): b"1",
    }


@pytest.mark.parametrize("content", [b"", b"not a zip", _archive(FILES)[:40]])
def test_bytes_that_are_no_zip_are_refused(content: bytes) -> None:
    assert _refusal(content) == (CoreErrorCode.ARCHIVE_UNREADABLE, {})


def test_an_archive_with_a_broken_file_is_refused() -> None:
    content = bytearray(_zip({"project.json": b"a project that will be damaged"}))
    at = content.index(b"damaged")
    content[at : at + 7] = b"DAMAGED"

    assert _refusal(bytes(content)) == (CoreErrorCode.ARCHIVE_UNREADABLE, {})


def test_an_archive_whose_directory_points_before_its_start_is_refused() -> None:
    """The end of a zip says where its list of files starts; a wrong place made the zip
    library raise a ``ValueError`` from a seek, which escaped."""
    content = bytearray(_archive(FILES))
    content[-6:-2] = struct.pack("<I", 0xFFFFFF00)

    assert _refusal(bytes(content)) == (CoreErrorCode.ARCHIVE_UNREADABLE, {})


def test_an_archive_with_a_name_that_is_not_utf8_is_refused() -> None:
    """A name marked as UTF-8 that is not made the zip library raise a
    ``UnicodeDecodeError``, which escaped."""
    content = bytearray(_archive(FILES))
    at = content.rindex("Se\u00f1al".encode())
    content[at + 2] = 0xFF

    assert _refusal(bytes(content)) == (CoreErrorCode.ARCHIVE_UNREADABLE, {})


def test_an_archive_with_any_bytes_changed_is_read_or_refused_and_never_raises() -> None:
    sound = _archive(FILES)
    changes = random.Random(5)  # noqa: S311 (a fixed seed: the same damage on every run)

    for _ in range(3000):
        damaged = bytearray(sound)
        for _ in range(changes.randint(1, 3)):
            damaged[changes.randrange(len(damaged))] = changes.randrange(256)
        parsed = read_archive(bytes(damaged))
        assert parsed.value is not None or parsed.issues


def test_a_mistake_of_ours_while_reading_is_not_taken_for_a_damaged_archive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_: object) -> bool:
        raise RuntimeError("a bug")

    monkeypatch.setattr(archive, "_is_a_name", broken)

    with pytest.raises(RuntimeError):
        read_archive(_archive(FILES))


@pytest.mark.parametrize(
    "name",
    [
        "../outside.vars",
        "scenes/../../outside.vars",
        "/etc/passwd",
        "scenes//a.sec",
        "./a.sec",
        "C:/a.sec",
        "scenes\\a.sec",
        "a.sec ",
        "a.sec.",
        "a\n.sec",
        "CON",
        "nul.vars",
        "COM1.vars",
        "aux/x.vars",
        "scenes/Lpt9.backup.sec",
    ],
)
def test_an_archive_with_a_path_that_is_not_safe_everywhere_is_refused(name: str) -> None:
    content = _zip({"project.json": b"{}", name: b"{}"})

    assert _refusal(content) == (CoreErrorCode.ARCHIVE_UNSAFE_PATH, {"path": name})


def test_an_archive_with_a_link_is_refused() -> None:
    link = zipfile.ZipInfo("link.vars")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    content = BytesIO()
    with zipfile.ZipFile(content, "w") as packed:
        packed.writestr(link, "/etc/passwd")

    assert _refusal(content.getvalue()) == (
        CoreErrorCode.ARCHIVE_UNSAFE_PATH,
        {"path": "link.vars"},
    )


def test_an_archive_with_two_names_that_are_one_file_on_windows_is_refused() -> None:
    content = _zip({"shop.vars": b"{}", "Shop.vars": b"{}"})

    assert _refusal(content) == (CoreErrorCode.ARCHIVE_DUPLICATE_PATH, {"path": "Shop.vars"})


def test_an_archive_with_one_name_written_in_the_two_ways_of_an_accent_is_refused() -> None:
    composed = unicodedata.normalize("NFC", "\u00e9.vars")
    decomposed = unicodedata.normalize("NFD", composed)

    content = _zip({composed: b"{}", decomposed: b"{}"})

    assert _refusal(content) == (CoreErrorCode.ARCHIVE_DUPLICATE_PATH, {"path": decomposed})


@pytest.mark.parametrize(
    ("entries", "refused"),
    [
        ({"a": b"{}", "a/b.vars": b"{}"}, "a/b.vars"),
        ({"a/b.vars": b"{}", "a": b"{}"}, "a"),
        ({"a/b/c.vars": b"{}", "A": b"{}"}, "A"),
    ],
)
def test_an_archive_with_a_file_where_a_folder_is_is_refused(
    entries: dict[str, bytes], refused: str
) -> None:
    assert _refusal(_zip(entries)) == (CoreErrorCode.ARCHIVE_DUPLICATE_PATH, {"path": refused})


def test_files_that_share_a_folder_are_read() -> None:
    content = _zip({"a/b.vars": b"1", "a/c.vars": b"2", "a/d/e.vars": b"3"})

    read = read_archive(content).value

    assert read is not None
    assert len(read) == 3


def test_an_archive_with_more_files_than_the_limit_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(archive, "MAX_FILES", 2)

    content = _zip({"a.vars": b"", "b.vars": b"", "c.vars": b""})

    assert _refusal(content) == (CoreErrorCode.ARCHIVE_TOO_MANY_FILES, {"max": 2})


def test_an_archive_that_unpacks_to_more_than_the_limit_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(archive, "MAX_BYTES", 2 * archive.BYTES_PER_MB)
    megabyte = bytes(archive.BYTES_PER_MB)

    content = _zip({f"{n}.vars": megabyte for n in range(3)})

    assert _refusal(content) == (CoreErrorCode.ARCHIVE_TOO_LARGE, {"max_mb": 2})


def test_an_archive_that_unpacks_to_exactly_the_limit_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(archive, "MAX_BYTES", 10)

    content = _archive({PurePosixPath("a.vars"): b"12345", PurePosixPath("b.vars"): b"67890"})

    assert read_archive(content).value is not None


def _writing_refusal(files: dict[PurePosixPath, bytes]) -> list[tuple[CoreErrorCode, object]]:
    written = write_archive(files)
    assert written.value is None
    return [(issue.code, dict(issue.params)) for issue in written.issues]


def test_a_project_with_two_names_that_are_one_file_somewhere_is_not_written() -> None:
    """It was written, and read_archive then refused what Primum itself wrote."""
    files = {PurePosixPath("Lights.vars"): b"{}", PurePosixPath("lights.vars"): b"{}"}

    found = _writing_refusal(files)

    assert found == [(CoreErrorCode.ARCHIVE_DUPLICATE_PATH, {"path": "lights.vars"})]


def test_a_project_with_names_not_every_system_holds_is_not_written_and_all_are_told() -> None:
    files = {
        PurePosixPath("CON.vars"): b"{}",
        PurePosixPath("ok.vars"): b"{}",
        PurePosixPath("scenes/a:b.sec"): b"{}",
    }

    found = _writing_refusal(files)

    assert found == [
        (CoreErrorCode.ARCHIVE_UNSAFE_PATH, {"path": "CON.vars"}),
        (CoreErrorCode.ARCHIVE_UNSAFE_PATH, {"path": "scenes/a:b.sec"}),
    ]


def test_a_project_over_the_limits_of_reading_is_not_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(archive, "MAX_FILES", 1)
    monkeypatch.setattr(archive, "MAX_BYTES", archive.BYTES_PER_MB)
    files = {PurePosixPath("a.vars"): bytes(archive.BYTES_PER_MB), PurePosixPath("b.vars"): b"1"}

    found = _writing_refusal(files)

    assert found == [
        (CoreErrorCode.ARCHIVE_TOO_MANY_FILES, {"max": 1}),
        (CoreErrorCode.ARCHIVE_TOO_LARGE, {"max_mb": 1}),
    ]


NAME_PARTS = (
    "a",
    "A",
    "b.vars",
    "B.VARS",
    "é.vars",
    "é.vars",
    "con",
    "Nul.sec",
    "..",
    ".",
    "x.",
    " x",
    "a:b",
    "tab\t",
    "scenes",
)


def test_what_is_written_reads_back_as_the_same_files() -> None:
    """Whatever paths a project has, its archive is either refused when written or read back
    whole: Primum never writes a file it cannot open."""
    choose = random.Random(11)  # noqa: S311 (a fixed seed: the same projects on every run)

    for _ in range(2000):
        files = {
            PurePosixPath(*choose.choices(NAME_PARTS, k=choose.randint(1, 3))): b"{}"
            for _ in range(choose.randint(1, 4))
        }
        written = write_archive(files)
        if written.value is None:
            assert written.issues
            continue
        assert read_archive(written.value).value == files
