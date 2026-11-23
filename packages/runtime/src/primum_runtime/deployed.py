"""The packages a board has been given, and which of them it runs (decision 0033).

A package gets to a board in two steps, on purpose: it is **stored** (checked, written,
nothing else changes), and then it is **activated** (it becomes what the board runs). The
one that was active stays, as the **previous** one, so that it can be put back.

They are kept in ``packages/`` under the data directory:

- ``<hash>.package.json``: a package, named by its own hash. At most three: the active one,
  the previous one and the one stored and not activated yet (``staged``).
- ``state.json``: which is which. Written whole and renamed into place: a power cut leaves
  the pointers before or the pointers after.

Nothing here runs anything: whoever runs packages asks which is active, and says when
another one is.
"""

import json
import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from primum_core.generated.model import Driver
from primum_core.json_values import as_object
from primum_runtime.errors import ErrorCode, PrimumError
from primum_runtime.package import LoadedPackage, check_content

log = logging.getLogger(__name__)

DIRECTORY = "packages"
STATE_NAME = "state.json"
SUFFIX = ".package.json"
VERSION = 1
# A package is a few hundred kilobytes at most; this is what is taken before it is even read.
MAX_BYTES = 8 * 1024 * 1024
_HASH = re.compile(r"sha256:[0-9a-f]{64}")


@dataclass(frozen=True)
class Pointers:
    """Which package is which, each by its hash; ``None`` where there is none."""

    active: str | None = None
    previous: str | None = None
    staged: str | None = None

    def __contains__(self, package: object) -> bool:
        return package is not None and package in (self.active, self.previous, self.staged)


class Deployed:
    """The packages kept in ``data_dir``. Used from one thread, the event loop's."""

    def __init__(self, data_dir: Path, manifests: Mapping[str, Driver], model: str) -> None:
        """``model`` is the board the service drives: a package for another is not for it,
        whatever profiles there are."""
        self._directory = data_dir / DIRECTORY
        self._manifests = manifests
        self._model = model

    def pointers(self) -> Pointers:
        """Which package is active, previous and staged. A state that is not there, or
        cannot be read, is no package at all: logged, never raised."""
        path = self._directory / STATE_NAME
        try:
            fields = as_object(json.loads(path.read_bytes().decode("utf-8")))
            if fields["version"] != VERSION:
                raise ValueError(f"not of version {VERSION}")
            names = {name: fields.get(name) for name in ("active", "previous", "staged")}
            wrong = [
                name for name, value in names.items() if value is not None and not _is_hash(value)
            ]
            if wrong:
                raise ValueError(f"not a hash: {', '.join(wrong)}")
        except FileNotFoundError:
            return Pointers()
        except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
            log.warning("the state of the packages (%s) cannot be used: %s", path, error)
            return Pointers()
        return Pointers(**{name: value for name, value in names.items() if isinstance(value, str)})

    def store(self, content: bytes) -> LoadedPackage:
        """Check a package and keep it as the staged one, replacing the one staged before.
        Nothing that runs changes.

        Fails, keeping nothing, with ``package.too_large`` (``max_bytes``), what
        ``primum_runtime.package`` reports for one this board cannot run,
        ``package.board_unsupported`` for one made for another board than the service's,
        and ``package.unwritable`` (``path``, ``detail``).
        """
        if len(content) > MAX_BYTES:
            raise PrimumError(ErrorCode.PACKAGE_TOO_LARGE, {"max_bytes": MAX_BYTES})
        loaded = self._checked(content, Path("uploaded" + SUFFIX))
        package = loaded.package.hash
        path = self._path(package)
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            _write(path, content)
        except OSError as error:
            raise _unwritable(path, error) from error
        self._point(replace(self.pointers(), staged=package))
        return loaded

    def load(self, package: str) -> LoadedPackage:
        """A package that is kept, read and checked again: a file is never trusted for
        having been checked once. ``package.not_stored`` (``hash``) for one that is not
        active, previous or staged; what ``load_package`` reports for one that no longer
        reads or that this board cannot run."""
        if package not in self.pointers():
            raise PrimumError(ErrorCode.PACKAGE_NOT_STORED, {"hash": package})
        path = self._path(package)
        try:
            content = path.read_bytes()
        except OSError as error:
            params = {"path": str(path), "detail": error.strerror or str(error)}
            raise PrimumError(ErrorCode.PACKAGE_UNREADABLE, params) from error
        return self._checked(content, path)

    def activate(self, package: str) -> Pointers:
        """Say that ``package`` is the one that runs now. The one that was becomes the
        previous one; activating the previous one swaps the two (a package put back can be
        undone again). The pointers as they are after."""
        before = self.pointers()
        if package not in before:
            raise PrimumError(ErrorCode.PACKAGE_NOT_STORED, {"hash": package})
        if package == before.active:
            return before
        staged = None if package == before.staged else before.staged
        after = Pointers(active=package, previous=before.active, staged=staged)
        self._point(after)
        return after

    def _checked(self, content: bytes, path: Path) -> LoadedPackage:
        loaded = check_content(content, path, self._manifests)
        model = loaded.package.board.model
        if model != self._model:
            params = {"board": model, "available": (self._model,)}
            raise PrimumError(ErrorCode.PACKAGE_BOARD_UNSUPPORTED, params)
        return loaded

    def _point(self, pointers: Pointers) -> None:
        """Write the pointers, then drop the packages none of them names."""
        path = self._directory / STATE_NAME
        document = {
            "version": VERSION,
            "active": pointers.active,
            "previous": pointers.previous,
            "staged": pointers.staged,
        }
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            _write(path, json.dumps(document).encode())
        except OSError as error:
            raise _unwritable(path, error) from error
        kept = {
            self._path(package).name
            for package in (pointers.active, pointers.previous, pointers.staged)
            if package
        }
        for file in self._directory.glob("*" + SUFFIX):
            if file.name not in kept:
                file.unlink(missing_ok=True)

    def _path(self, package: str) -> Path:
        if not _is_hash(package):  # it becomes a file name: nothing but a hash gets there
            raise PrimumError(ErrorCode.PACKAGE_NOT_STORED, {"hash": package})
        return self._directory / (package.removeprefix("sha256:") + SUFFIX)


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def _write(path: Path, content: bytes) -> None:
    """Whole, on the card, then renamed into place, and the name on the card too."""
    temporary = path.with_suffix(".tmp")
    with temporary.open("wb") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _unwritable(path: Path, error: OSError) -> PrimumError:
    params = {"path": str(path), "detail": error.strerror or str(error)}
    return PrimumError(ErrorCode.PACKAGE_UNWRITABLE, params)
