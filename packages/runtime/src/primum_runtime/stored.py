"""The values of persistent variables, kept where they survive the service (decision 0031).

A variable marked ``persistent`` keeps its value across a restart and a power cut: a counter
of visits, a brightness set from the phone. The values are kept in the data directory, in
one file, for one project: the values of another project are not this one's, and a new
package of the same project finds them.

The file is written whole and then renamed into place, so it is never half written. What
is kept is never replaced by values that drop some of it without a copy left beside it
(``set_aside``): another project's, or a new package that no longer takes them. Reading
never fails the service: a file that is not there, cannot be read, does not say what it
should or is of another project gives no values, and the variables start at their initial
ones. What a value is worth against its variable (its type, its limits) is for whoever has
the variables to say.
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

FILE_NAME = "variables.json"
ASIDE_NAME = "variables.json.bak"
VERSION = 1
# One write at a time: the last save of a service that stops must not cross one under way.
_writing = threading.Lock()


def write(directory: Path, project: UUID, values: Mapping[UUID, Value]) -> None:
    """Keep ``values`` (by the id of each variable) as those of ``project``, replacing what
    was kept before.

    Fails with ``variables.unwritable`` (``path``, ``detail``); what was kept before stays.
    """
    path = directory / FILE_NAME
    document = {
        "version": VERSION,
        "project": str(project),
        "values": {str(variable): value for variable, value in values.items()},
    }
    temporary = path.with_suffix(".tmp")
    try:
        with _writing, temporary.open("w", encoding="utf-8") as file:
            json.dump(document, file)
            file.flush()
            os.fsync(file.fileno())  # on the card, or a power cut would leave the name empty
            temporary.replace(path)
            _sync_directory(directory)
    except OSError as error:
        params = {"path": str(path), "detail": error.strerror or str(error)}
        raise PrimumError(ErrorCode.VARIABLES_UNWRITABLE, params) from error


def _sync_directory(directory: Path) -> None:
    """Have the new name on the card too, not only the content: until then a power cut
    would bring the file before back."""
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def set_aside(directory: Path) -> None:
    """Copy what is kept to ``variables.json.bak`` before it is replaced by values that
    drop some of it: another project's, a file that could not be read, values a new package
    no longer takes. Going back must be able to find them. Nothing kept, nothing done; a
    copy that fails is logged, and stops nothing."""
    path = directory / FILE_NAME
    try:
        content = path.read_bytes()
        (directory / ASIDE_NAME).write_bytes(content)
    except FileNotFoundError:
        return
    except OSError as error:
        log.warning("the kept variables (%s) could not be set aside: %s", path, error)
        return
    log.info("the kept variables were set aside in %s", directory / ASIDE_NAME)


def read(directory: Path, project: UUID) -> dict[UUID, Value]:
    """The values kept for ``project`` in ``directory``, by the id of each variable; none
    when nothing is kept for it. Never fails: what cannot be used is logged and left."""
    path = directory / FILE_NAME
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return {}
    except OSError as error:
        log.warning("the kept variables (%s) cannot be read: %s", path, error)
        return {}
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
        log.warning("the kept variables (%s) do not say what they should: %s", path, error)
        return {}
    if kept_for != project:
        log.info("the kept variables (%s) are of another project: not used", path)
        return {}
    return values


def _value(value: object) -> Value:
    if not isinstance(value, bool | int | float | str):
        raise TypeError(f"not a value: {value!r}")
    return value
