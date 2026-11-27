"""The ``.primum`` file: a whole project as one zip of its folder (``docs/specs/workspace.md``).

A project is saved, shared and sent to a board as one file. Here it is bytes in, files out,
and back: nothing is read from or written to a disk, the zip is made and read in memory
(decision 0037 says why ``io`` is allowed in this module alone).

Writing is deterministic: the same files give the same bytes, whatever the machine and the
day, so two copies of a project can be compared. Reading trusts nothing: an archive comes from
a phone, a mail or the Internet. It has limits of size and number, and a path that would leave
the project's folder, or that two systems would read differently, refuses the whole archive.
What the files say is for ``load_workspace``.
"""

import stat
import zipfile
import zlib
from collections.abc import Iterator, Mapping
from io import BytesIO
from pathlib import PurePosixPath

from primum_core.errors import CoreErrorCode, Issue
from primum_core.formats import Parsed

type Files = Mapping[PurePosixPath, bytes]

MAX_FILES = 2000
MAX_BYTES = 64 * 1024 * 1024  # of every file together, unpacked; audio will ask for more
BYTES_PER_MB = 1024 * 1024
# What every entry is written with, so the bytes do not depend on who writes them.
EPOCH = (1980, 1, 1, 0, 0, 0)  # the first date a zip can hold
UNIX = 3
FILE_MODE = (stat.S_IFREG | 0o644) << 16
ENCRYPTED = 0x1
FORBIDDEN_IN_A_NAME = frozenset('\\:*?"<>|')  # no Windows folder can hold them
FIRST_PRINTABLE = " "


class _RefusedError(Exception):
    """An archive that is not taken, with the issue that says why."""

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.code)
        self.issue = issue


def write_archive(files: Files) -> bytes:
    """The ``.primum`` file of a project: its files, by path, in one zip."""
    content = BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        for path in sorted(files):
            archive.writestr(_entry(path), files[path])
    return content.getvalue()


def _entry(path: PurePosixPath) -> zipfile.ZipInfo:
    entry = zipfile.ZipInfo(path.as_posix(), EPOCH)
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.create_system = UNIX
    entry.external_attr = FILE_MODE
    return entry


def read_archive(content: bytes) -> Parsed[Files]:
    """The files of a ``.primum`` file, by path, or the issue that refuses it."""
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            return Parsed(dict(_files(archive)))
    except _RefusedError as refused:
        return Parsed(None, (refused.issue,))
    # Not a zip, cut short, a checksum that fails, a compression Python does not have.
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError):
        return Parsed(None, (Issue(CoreErrorCode.ARCHIVE_UNREADABLE),))


def _files(archive: zipfile.ZipFile) -> Iterator[tuple[PurePosixPath, bytes]]:
    entries = [entry for entry in archive.infolist() if not entry.is_dir()]
    if len(entries) > MAX_FILES:
        raise _RefusedError(Issue(CoreErrorCode.ARCHIVE_TOO_MANY_FILES, {"max": MAX_FILES}))
    seen: set[str] = set()
    left = MAX_BYTES
    for entry in entries:
        path = _safe_path(entry)
        folded = path.as_posix().casefold()  # Shop.vars and shop.vars are one file on Windows
        if folded in seen:
            params = {"path": entry.filename}
            raise _RefusedError(Issue(CoreErrorCode.ARCHIVE_DUPLICATE_PATH, params))
        seen.add(folded)
        data = _read(archive, entry, left)
        left -= len(data)
        yield path, data


def _safe_path(entry: zipfile.ZipInfo) -> PurePosixPath:
    """The path of an entry inside the project's folder, on any system: relative, with no
    ``..``, no name a Windows folder cannot hold, and a plain file, not a link."""
    name = entry.filename
    parts = name.split("/")
    # No type at all is what a program that knows nothing of Unix writes: a plain file.
    plain = stat.S_IFMT(entry.external_attr >> 16) in {stat.S_IFREG, 0}
    if not plain or entry.flag_bits & ENCRYPTED or not all(_is_a_name(part) for part in parts):
        raise _RefusedError(Issue(CoreErrorCode.ARCHIVE_UNSAFE_PATH, {"path": name}))
    return PurePosixPath(*parts)


def _is_a_name(part: str) -> bool:
    if part in {"", ".", ".."} or part != part.strip() or part.endswith("."):
        return False
    return not any(char in FORBIDDEN_IN_A_NAME or char < FIRST_PRINTABLE for char in part)


def _read(archive: zipfile.ZipFile, entry: zipfile.ZipInfo, left: int) -> bytes:
    """The content of an entry, never unpacking more than ``left`` bytes: the size an entry
    declares is whatever its writer wanted to say."""
    with archive.open(entry) as packed:
        data = packed.read(left + 1)
    if len(data) > left:
        params = {"max_mb": MAX_BYTES // BYTES_PER_MB}
        raise _RefusedError(Issue(CoreErrorCode.ARCHIVE_TOO_LARGE, params))
    return data
