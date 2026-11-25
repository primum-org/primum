"""The values of persistent variables, kept where they survive the service (decision 0031).

A variable marked ``persistent`` keeps its value across a restart and a power cut: a counter
of visits, a brightness set from the phone. The values are kept in the data directory, in
``variables/``, one file per project, named by the project's id: the values of a project are
its own, a new package of the same project finds them, and running another project on the
board for a while does not touch them.

A file is written whole and then renamed into place, so it is never half written. What is
kept is never replaced by values that drop some of it without a copy left beside it
(``set_aside``): a file that could not be read, or values a new package no longer takes.
Reading never fails the service: a file that is not there, cannot be read or does not say
what it should gives no values, and the variables start at their initial ones. What a value
is worth against its variable (its type, its limits) is for whoever has the variables to say.

Until block 4.5b the values were one file for the whole board, ``variables.json``, of one
project. It is still read, for the project it names, when that project has no file yet.
"""

import json
import logging
import os
import threading
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

from primum_core.json_values import as_object, as_str
from primum_core.values import Value
from primum_runtime.errors import ErrorCode, PrimumError

log = logging.getLogger(__name__)

DIRECTORY = "variables"
LEGACY_NAME = "variables.json"  # the one file of before, for one project
ASIDE_SUFFIX = ".bak"
VERSION = 1
# One write at a time: the last save of a service that stops must not cross one under way.
_writing = threading.Lock()


def path(directory: Path, project: UUID) -> Path:
    """Where the values of ``project`` are kept under the data directory."""
    return directory / DIRECTORY / f"{project}.json"


def write(directory: Path, project: UUID, values: Mapping[UUID, Value]) -> None:
    """Keep ``values`` (by the id of each variable) as those of ``project``, replacing what
    was kept for it before. What is kept for other projects stays.

    Fails with ``variables.unwritable`` (``path``, ``detail``); what was kept before stays.
    """
    file = path(directory, project)
    document = {
        "version": VERSION,
        "project": str(project),
        "values": {str(variable): value for variable, value in values.items()},
    }
    temporary = file.with_suffix(".tmp")
    try:
        with _writing:
            file.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("w", encoding="utf-8") as written:
                json.dump(document, written)
                written.flush()
                os.fsync(written.fileno())  # on the card, or a power cut would leave it empty
            temporary.replace(file)
            _sync_directory(file.parent)
    except OSError as error:
        params = {"path": str(file), "detail": error.strerror or str(error)}
        raise PrimumError(ErrorCode.VARIABLES_UNWRITABLE, params) from error


def _sync_directory(directory: Path) -> None:
    """Have the new name on the card too, not only the content: until then a power cut
    would bring the file before back."""
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def set_aside(directory: Path, project: UUID) -> None:
    """Copy what is kept for ``project`` to a ``.bak`` beside it, before it is replaced by
    values that drop some of it: a file that could not be read, values a new package no
    longer takes. Going back must be able to find them. Nothing kept, nothing done; a copy
    that fails is logged, and stops nothing."""
    file = _kept_in(directory, project)
    if file is None:
        return
    aside = path(directory, project).with_name(f"{project}.json{ASIDE_SUFFIX}")
    try:
        aside.parent.mkdir(parents=True, exist_ok=True)
        aside.write_bytes(file.read_bytes())
    except OSError as error:
        log.warning("the kept variables (%s) could not be set aside: %s", file, error)
        return
    log.info("the kept variables were set aside in %s", aside)


def read(directory: Path, project: UUID) -> dict[UUID, Value]:
    """The values kept for ``project`` in ``directory``, by the id of each variable; none
    when nothing is kept for it. Never fails: what cannot be used is logged and left."""
    file = _kept_in(directory, project)
    if file is None:
        return {}
    values = _read(file)
    return {} if values is None or values[0] != project else values[1]


def _kept_in(directory: Path, project: UUID) -> Path | None:
    """The file that has the values of ``project``: its own, or the one file of before when
    that one is this project's (or cannot be told whose it is: then it is set aside before
    anything is written, and never read)."""
    own = path(directory, project)
    if own.exists():
        return own
    legacy = directory / LEGACY_NAME
    if not legacy.exists():
        return None
    values = _read(legacy)
    return legacy if values is None or values[0] == project else None


def _read(file: Path) -> tuple[UUID, dict[UUID, Value]] | None:
    """The project a file is of, and its values; ``None``, logged, for one that cannot be
    read or does not say what it should."""
    try:
        content = file.read_bytes()
    except OSError as error:
        log.warning("the kept variables (%s) cannot be read: %s", file, error)
        return None
    try:
        # Whatever the bytes are: not text (that is a ValueError too), not JSON, nested
        # past what the reader takes, or JSON that says something else.
        fields = as_object(json.loads(content.decode("utf-8")))
        if fields["version"] != VERSION:
            raise ValueError(f"not of version {VERSION}")
        kept_for = UUID(as_str(fields["project"]))
        values = {
            UUID(variable): _value(value) for variable, value in as_object(fields["values"]).items()
        }
    except (ValueError, KeyError, TypeError, RecursionError) as error:
        log.warning("the kept variables (%s) do not say what they should: %s", file, error)
        return None
    return kept_for, values


def _value(value: object) -> Value:
    if not isinstance(value, bool | int | float | str):
        raise TypeError(f"not a value: {value!r}")
    return value
