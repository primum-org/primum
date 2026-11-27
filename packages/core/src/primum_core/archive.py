"""The ``.primum`` file: a whole project as one zip of its folder (``docs/specs/workspace.md``).

A project is saved, shared and sent to a board as one file. Here it is bytes in, files out,
and back: nothing is read from or written to a disk, the zip is made and read in memory
(decision 0037 says why ``io`` is allowed in this module alone).

Writing does not depend on the day, the machine's settings or the order the files come in:
the same files give the same bytes wherever the same zlib compresses them. Reading trusts
nothing: an archive comes from
a phone, a mail or the Internet. It has limits of size and number, and a path that would leave
the project's folder, or that two systems would read differently, refuses the whole archive.
What the files say is for ``load_workspace``.
"""

import stat
import unicodedata
import zipfile
from collections.abc import Generator, Iterator, Mapping
from contextlib import contextmanager
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
# Devices to Windows, with any extension and in any case: CON, nul.vars, Com1.sec.
DEVICE_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{n}" for n in range(1, 10)}
    | {f"lpt{n}" for n in range(1, 10)}
)


class _RefusedError(Exception):
    """An archive that is not taken, with the issue that says why."""

    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.code)
        self.issue = issue


def write_archive(files: Files) -> Parsed[bytes]:
    """The ``.primum`` file of a project: its files, by path, in one zip. A project that
    ``read_archive`` could not read back is not written: every issue that says why comes back
    instead (a folder that reads on Linux may hold ``Lights.vars`` and ``lights.vars``)."""
    issues = _writing_issues(files)
    if issues:
        return Parsed(None, issues)
    content = BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        for path in sorted(files):
            archive.writestr(_entry(path), files[path])
    return Parsed(content.getvalue())


def _writing_issues(files: Files) -> tuple[Issue, ...]:
    """What reading the archive of ``files`` would refuse, all of it: who writes it has every
    file to rename at once."""
    issues: list[Issue] = []
    if len(files) > MAX_FILES:
        issues.append(Issue(CoreErrorCode.ARCHIVE_TOO_MANY_FILES, {"max": MAX_FILES}))
    if sum(len(content) for content in files.values()) > MAX_BYTES:
        issues.append(_too_large())
    taken = _Taken()
    for path in sorted(files):
        name = path.as_posix()
        if not _is_safe_name(name):
            issues.append(_unsafe(name))
        elif issue := taken.add(path, name):
            issues.append(issue)
    return tuple(issues)


def _entry(path: PurePosixPath) -> zipfile.ZipInfo:
    entry = zipfile.ZipInfo(path.as_posix(), EPOCH)
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.create_system = UNIX
    entry.external_attr = FILE_MODE
    return entry


def read_archive(content: bytes) -> Parsed[Files]:
    """The files of a ``.primum`` file, by path, or the issue that refuses it."""
    try:
        return Parsed(dict(_files(content)))
    except _RefusedError as refused:
        return Parsed(None, (refused.issue,))


@contextmanager
def _unpacking() -> Generator[None]:
    """Whatever the zip library raises on bytes that are not a sound zip becomes
    ``archive.unreadable``. It raises many things (a damaged zip is a ``ValueError`` from a
    seek, a ``UnicodeDecodeError`` from a name, a ``zlib.error``...) and what it raises changes
    with its version, so none is named. Only calls to the library go in here: a mistake of
    ours must not be taken for a damaged file."""
    try:
        yield
    except _RefusedError:
        raise
    except Exception as damaged:
        raise _RefusedError(Issue(CoreErrorCode.ARCHIVE_UNREADABLE)) from damaged


def _files(content: bytes) -> Iterator[tuple[PurePosixPath, bytes]]:
    with _unpacking():
        archive = zipfile.ZipFile(BytesIO(content))
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
    if len(entries) > MAX_FILES:
        raise _RefusedError(Issue(CoreErrorCode.ARCHIVE_TOO_MANY_FILES, {"max": MAX_FILES}))
    taken = _Taken()
    left = MAX_BYTES
    for entry in entries:
        path = _safe_path(entry)
        if issue := taken.add(path, entry.filename):
            raise _RefusedError(issue)
        with _unpacking():
            data = _read(archive, entry, left)
        left -= len(data)
        yield path, data


class _Taken:
    """The places the files read so far take on a disk, on any system: a second file cannot
    go where one is, nor where a folder is, nor inside what is a file."""

    def __init__(self) -> None:
        self._files: set[str] = set()
        self._folders: set[str] = set()

    def add(self, path: PurePosixPath, name: str) -> Issue | None:
        """Take the place of ``path``, or say why it is taken already."""
        place = _place(path)
        above = {_place(parent) for parent in path.parents[:-1]}
        if place in self._files | self._folders or above & self._files:
            return Issue(CoreErrorCode.ARCHIVE_DUPLICATE_PATH, {"path": name})
        self._files.add(place)
        self._folders |= above
        return None


def _place(path: PurePosixPath) -> str:
    """Where a path lands on a disk that tells neither capitals apart (Windows, macOS) nor
    the two ways of writing an accent (macOS): ``Señal.vars`` is one file however written."""
    return unicodedata.normalize("NFC", path.as_posix()).casefold()


def _safe_path(entry: zipfile.ZipInfo) -> PurePosixPath:
    """The path of an entry inside the project's folder, on any system: relative, with no
    ``..``, no name a Windows folder cannot hold, and a plain file, not a link."""
    name = entry.filename
    # No type at all is what a program that knows nothing of Unix writes: a plain file.
    plain = stat.S_IFMT(entry.external_attr >> 16) in {stat.S_IFREG, 0}
    if not plain or entry.flag_bits & ENCRYPTED or not _is_safe_name(name):
        raise _RefusedError(_unsafe(name))
    return PurePosixPath(*name.split("/"))


def _unsafe(name: str) -> Issue:
    return Issue(CoreErrorCode.ARCHIVE_UNSAFE_PATH, {"path": name})


def _is_safe_name(name: str) -> bool:
    """Whether every part of a path, ``/`` between them, is a name any system can hold."""
    return all(_is_a_name(part) for part in name.split("/"))


def _is_a_name(part: str) -> bool:
    if part in {"", ".", ".."} or part != part.strip() or part.endswith("."):
        return False
    if part.split(".")[0].casefold() in DEVICE_NAMES:
        return False
    return not any(char in FORBIDDEN_IN_A_NAME or char < FIRST_PRINTABLE for char in part)


def _read(archive: zipfile.ZipFile, entry: zipfile.ZipInfo, left: int) -> bytes:
    """The content of an entry, never unpacking more than ``left`` bytes: the size an entry
    declares is whatever its writer wanted to say."""
    with archive.open(entry) as packed:
        data = packed.read(left + 1)
    if len(data) > left:
        raise _RefusedError(_too_large())
    return data


def _too_large() -> Issue:
    return Issue(CoreErrorCode.ARCHIVE_TOO_LARGE, {"max_mb": MAX_BYTES // BYTES_PER_MB})
