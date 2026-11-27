"""Editing a project: an operation in, the project's files with the change or why not out.

Every edit of a project, from the web UI, Primum Studio or the MCP server, is an operation
applied here (``docs/specs/operations.md``, decision 0037). A project is its files, as
``load_workspace`` takes them: path relative to the project's folder → content. The files that
come back are new; the ones given are never changed.

An operation is refused when it is not one (its shape, the fields of its ``op``), when what it
names is not in the project, or when the file it changes would have a problem of its own that
it did not have before: a name too long, a minimum above the maximum. What the change means
for the rest of the project is not judged here: a project may be left with problems, as one
being built is, and ``load_workspace`` lists them.
"""

import json
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from uuid import UUID

from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.formats import (
    Parsed,
    decode,
    has_half_a_character,
    read_manifest,
    read_project_file,
)
from primum_core.generated.model import Variable, Variables, parse_operation
from primum_core.generated.schemas import SCHEMAS
from primum_core.json_values import JsonObject, as_list, as_object, is_object
from primum_core.pointers import Step, field_name
from primum_core.references import LocatedContent
from primum_core.schema_validation import validate
from primum_core.variants import check_variants
from primum_core.workspace import MANIFEST

type Files = Mapping[PurePosixPath, bytes]

OPERATION_SCHEMA = "operation.schema.json"
VARIABLES_SUFFIX = ".vars"
OP_FIELD = "op"
CLEAR_FIELD = "clear"
INDENT = 2
# Issues of an operation point at no file: this place is only for reading it, and is dropped.
NOWHERE = Location(PurePosixPath())


@dataclass(frozen=True)
class _Kind:
    """What an ``op`` takes: the field that names what it changes, if it is not the project
    itself, the fields it may set and the ones it may take away."""

    target: str | None
    settable: frozenset[str]
    clearable: frozenset[str]


def _kind(target: str | None, settable: str, clearable: str) -> _Kind:
    return _Kind(target, frozenset(settable.split()), frozenset(clearable.split()))


KINDS: Mapping[str, _Kind] = {
    "set_project": _kind(None, "name description timeZone", "description timeZone"),
    "set_variable": _kind(
        "variable", "label initial min max step persistent setting", "label min max step"
    ),
}


@dataclass(frozen=True)
class _Target:
    """The object an operation changes: its file, where it is inside it, and the order its
    fields are written in (the one of its schema)."""

    path: PurePosixPath
    steps: tuple[Step, ...]
    field_order: Sequence[str]


def apply_operation(files: Files, operation: object) -> Parsed[Files]:
    """The project's files with ``operation`` (a decoded JSON document) applied, or the issues
    that refuse it. Only the file it changes is new; it is written again whole."""
    issues = tuple(_operation_issues(operation))
    if issues:
        return Parsed(None, issues)
    document = as_object(operation)
    kind = KINDS[parse_operation(document).op]
    target = _target(files, kind, document)
    if not isinstance(target, _Target):
        return Parsed(None, target)
    before = files[target.path]
    after = _written(_changed(decode(before, NOWHERE), target, kind, document))
    added = _own_issues(target.path, after) - _own_issues(target.path, before)
    if added:
        return Parsed(None, tuple(sorted(added, key=_by_place)))
    return Parsed({**files, target.path: after})


def _operation_issues(operation: object) -> Iterator[Issue]:
    """What makes ``operation`` not one: its shape, then the fields of its ``op``."""
    if has_half_a_character(operation):
        yield Issue(CoreErrorCode.OPERATION_INVALID_TEXT)
        return
    not_numbers = tuple(_not_a_number_issues(operation))
    if not_numbers:
        yield from not_numbers
        return
    malformed = validate(OPERATION_SCHEMA, operation, NOWHERE)
    if malformed:
        yield from (replace(issue, location=None) for issue in malformed)
        return
    document = as_object(operation)
    kind = KINDS[parse_operation(document).op]
    cleared = [str(name) for name in as_list(document.get(CLEAR_FIELD, []))]
    if kind.target is not None and kind.target not in document:
        yield Issue(CoreErrorCode.SCHEMA_MISSING_FIELD, {"field": kind.target})
    for name in document:
        if name not in {OP_FIELD, CLEAR_FIELD, kind.target} | kind.settable:
            yield Issue(CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, {"field": name})
    for index, name in enumerate(cleared):
        if name not in kind.clearable:
            field = field_name((CLEAR_FIELD, index))
            yield Issue(CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, {"field": field})
        elif name in document:
            yield Issue(CoreErrorCode.OPERATION_SET_AND_CLEARED, {"field": name})


def _not_a_number_issues(operation: object) -> Iterator[Issue]:
    """Numbers JSON does not have and no variable can hold: ``NaN``, an infinity, an integer
    of hundreds of digits. Reading a file turns them away (``primum_core.formats``); an
    operation arrives already decoded, by whoever calls, so they are turned away here, before
    they reach a file and are blamed on it."""
    if not is_object(operation):
        return
    for name, value in operation.items():
        if isinstance(value, int | float) and not _is_finite(value):
            yield Issue(CoreErrorCode.SCHEMA_EXPECTED_NUMBER, {"field": name})


def _is_finite(value: float) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:  # an integer too large for any float
        return False


def _target(files: Files, kind: _Kind, operation: JsonObject) -> _Target | tuple[Issue, ...]:
    """What ``operation`` changes, or the issues that say it cannot be found."""
    if kind.target is None:
        return _manifest_target(files)
    return _variable_target(files, UUID(str(operation[kind.target])))


def _manifest_target(files: Files) -> _Target | tuple[Issue, ...]:
    if MANIFEST not in files:
        return (Issue(CoreErrorCode.PROJECT_MANIFEST_MISSING, {}, Location(MANIFEST)),)
    unreadable = read_manifest(MANIFEST, files[MANIFEST]).issues
    if unreadable:
        return unreadable
    return _Target(MANIFEST, (), _field_order(SCHEMAS["project.schema.json"]))


def _variable_target(files: Files, variable: UUID) -> _Target | tuple[Issue, ...]:
    """The variable with that id. A ``.vars`` file that cannot be read has no variables to
    change: it is fixed by hand, or replaced. An id that two variables have names neither:
    changing the first found could be changing the one the person is not looking at."""
    schema = as_object(as_object(SCHEMAS["variables.schema.json"]["$defs"])["variable"])
    found = [
        _Target(path, ("variables", index), _field_order(schema))
        for path in sorted(files)
        for index, candidate in enumerate(_variables(path, files[path]))
        if candidate.id == variable
    ]
    if not found:
        return (Issue(CoreErrorCode.OPERATION_UNKNOWN_VARIABLE, {"id": str(variable)}),)
    if len(found) > 1:
        return (Issue(CoreErrorCode.ID_DUPLICATE, {"id": str(variable)}),)
    return found[0]


def _variables(path: PurePosixPath, content: bytes) -> tuple[Variable, ...]:
    if path.suffix.lower() != VARIABLES_SUFFIX:
        return ()
    read = read_project_file(path, content).value
    return read.variables if isinstance(read, Variables) else ()


def _field_order(schema: JsonObject) -> Sequence[str]:
    return tuple(as_object(schema["properties"]))


def _changed(document: object, target: _Target, kind: _Kind, operation: JsonObject) -> object:
    """``document`` with the object at the target's place changed as ``operation`` says."""
    if not target.steps:
        return _edited(as_object(document), target.field_order, kind, operation)
    step, *rest = target.steps
    inner = replace(target, steps=tuple(rest))
    if isinstance(step, int):
        items = as_list(document)
        changed = _changed(items[step], inner, kind, operation)
        return [*items[:step], changed, *items[step + 1 :]]
    fields = as_object(document)
    return {**fields, step: _changed(fields[step], inner, kind, operation)}


def _edited(
    fields: JsonObject, order: Sequence[str], kind: _Kind, operation: JsonObject
) -> JsonObject:
    """The fields the operation sets, set, and the ones it clears, gone; written in the order
    of the schema, so a file reads the same whoever edited it."""
    cleared = as_list(operation.get(CLEAR_FIELD, []))
    set_ = {name: value for name, value in operation.items() if name in kind.settable}
    merged = {**fields, **set_}
    return {name: merged[name] for name in order if name in merged and name not in cleared}


def _written(document: object) -> bytes:
    """A file as Primum writes it: UTF-8, two spaces, a line end at the end."""
    return (json.dumps(document, indent=INDENT, ensure_ascii=False) + "\n").encode()


def _own_issues(path: PurePosixPath, content: bytes) -> frozenset[Issue]:
    """The problems a file has on its own, whatever the rest of the project says."""
    if path == MANIFEST:
        return frozenset(read_manifest(path, content).issues)
    parsed = read_project_file(path, content)
    if parsed.value is None:
        return frozenset(parsed.issues)
    location = Location(path, file_id=parsed.value.id)
    return frozenset(check_variants(LocatedContent(parsed.value, location)))


def _by_place(issue: Issue) -> tuple[str, str]:
    return (issue.location.pointer if issue.location else "", issue.code)
