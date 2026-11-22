"""The values of persistent variables, kept where they survive the service (decision 0031).

A variable marked ``persistent`` keeps its value across a restart and a power cut: a counter
of visits, a brightness set from the phone. The values are kept in the data directory, in
one file, for one project: the values of another project are not this one's, and a new
package of the same project finds them.

The file is written whole and then renamed into place, so it is never half written. Reading
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
    except OSError as error:
        params = {"path": str(path), "detail": error.strerror or str(error)}
        raise PrimumError(ErrorCode.VARIABLES_UNWRITABLE, params) from error


def read(directory: Path, project: UUID) -> dict[UUID, Value]:
    """The values kept for ``project`` in ``directory``, by the id of each variable; none
    when nothing is kept for it. Never fails: what cannot be used is logged and left."""
    path = directory / FILE_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as error:
        log.warning("the kept variables (%s) cannot be read: %s", path, error)
        return {}
    try:
        fields = as_object(json.loads(text))
        if fields["version"] != VERSION:
            raise ValueError(f"not of version {VERSION}")
        kept_for = UUID(as_str(fields["project"]))
        values = {
            UUID(variable): _value(value) for variable, value in as_object(fields["values"]).items()
        }
    except (ValueError, KeyError, TypeError) as error:
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
