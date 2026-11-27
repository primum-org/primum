"""Editing a project: an operation in, the project's files with the change or why not out.

Every edit of a project, from the web UI, Primum Studio or the MCP server, is an operation
applied here (``docs/specs/operations.md``, decision 0037). A project is its files, as
``load_workspace`` takes them: path relative to the project's folder → content. The files that
come back are new; the ones given are never changed.

An operation is refused when it is not one (its shape, the fields of its ``op``), when what it
names is not in the project, or when the object it changes would have a problem of its own
that it did not have before: a name too long, a minimum above the maximum. What the change
means for the rest of the project is not judged here: a project may be left with problems, as
one being built is, and ``load_workspace`` lists them.

A file is edited as the JSON document it is, so a file with problems can be edited too: an
uploaded project that does not validate is fixed with the same operations.
"""

import json
import math
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from uuid import UUID

from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.formats import (
    Parsed,
    decode,
    file_id,
    has_half_a_character,
    read_manifest,
)
from primum_core.generated.model import parse_operation, parse_variable
from primum_core.generated.schemas import SCHEMAS
from primum_core.json_values import JsonObject, as_list, as_object, is_array, is_object
from primum_core.pointers import Step, field_name, pointer
from primum_core.schema_validation import validate, validate_definition
from primum_core.variants import check_variable
from primum_core.workspace import MANIFEST

type Files = Mapping[PurePosixPath, bytes]
type Document = dict[str, object]
type IssuesOf = Callable[[JsonObject], frozenset[Issue]]

OPERATION_SCHEMA = "operation.schema.json"
PROJECT_SCHEMA = "project.schema.json"
VARIABLES_SCHEMA = "variables.schema.json"
VARIABLE_DEFINITION = "variable"
VARIABLES_SUFFIX = ".vars"
VARIABLES_FIELD = "variables"
ID_FIELD = "id"
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
    """The object an operation changes: its file, decoded, and the schema of the file, where
    it is inside it, the order its fields are written in (the one of its schema) and the
    problems it has on its own."""

    path: PurePosixPath
    document: Document
    schema: str
    steps: tuple[Step, ...]
    field_order: Sequence[str]
    issues_of: IssuesOf


def apply_operation(files: Files, operation: object) -> Parsed[Files]:
    """The project's files with ``operation`` (a decoded JSON document) applied, or the issues
    that refuse it. Only the file it changes is new; it is written again whole. An operation
    that changes nothing gives back the files it was given."""
    issues = tuple(_operation_issues(operation))
    if issues:
        return Parsed(None, issues)
    document = as_object(operation)
    kind = KINDS[parse_operation(document).op]
    target = _target(files, kind, document)
    if not isinstance(target, _Target):
        return Parsed(None, target)
    before = target.document
    after = as_object(_changed(before, target.steps, target.field_order, kind, document))
    if not _holds_only_json(after):
        return Parsed(None, _unwritable(target, after))
    if _holds_only_json(before) and _dumped(before) == _dumped(after):
        return Parsed(files)
    added = target.issues_of(after) - target.issues_of(before)
    if added:
        return Parsed(None, tuple(sorted(added, key=_by_place)))
    return Parsed({**files, target.path: _written(after)})


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
    """Numbers JSON does not have and no float can hold: ``NaN``, an infinity, an integer of
    hundreds of digits. Reading a file turns them away (``primum_core.formats``); an operation
    arrives already decoded, by whoever calls, so they are turned away here, before they reach
    a file and are blamed on it."""
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
    """The manifest, if it is a JSON object: one that does not validate can still be fixed."""
    if MANIFEST not in files:
        return (Issue(CoreErrorCode.PROJECT_MANIFEST_MISSING, {}, Location(MANIFEST)),)
    document = _object(MANIFEST, files[MANIFEST])
    if isinstance(document, Issue):
        return (document,)
    order = _field_order(SCHEMAS[PROJECT_SCHEMA])
    return _Target(MANIFEST, document, PROJECT_SCHEMA, (), order, _manifest_issues)


def _manifest_issues(document: JsonObject) -> frozenset[Issue]:
    return frozenset(read_manifest(MANIFEST, _written(document)).issues)


def _variable_target(files: Files, variable: UUID) -> _Target | tuple[Issue, ...]:
    """The variable with that id, looked for in the JSON of every ``.vars`` file, whatever
    problems the file has. A file that is not a JSON object cannot be looked in: when the
    variable is not found, its problem comes with the answer. An id that two variables have
    names neither: changing the first found could be changing the one the person is not
    looking at."""
    order = _field_order(_definition(VARIABLES_SCHEMA, VARIABLE_DEFINITION))
    found: list[_Target] = []
    unsearched: list[Issue] = []
    for path in sorted(files):
        if path.suffix.lower() != VARIABLES_SUFFIX:
            continue
        document = _object(path, files[path])
        if isinstance(document, Issue):
            unsearched.append(document)
            continue
        if not is_array(document.get(VARIABLES_FIELD)):
            unsearched += _variables_problem(path, document)
            continue
        for index in _indices_with_id(document.get(VARIABLES_FIELD), variable):
            steps: tuple[Step, ...] = (VARIABLES_FIELD, index)
            issues_of = _variable_issues(path, steps)
            found.append(_Target(path, document, VARIABLES_SCHEMA, steps, order, issues_of))
    if not found:
        return (Issue(CoreErrorCode.OPERATION_UNKNOWN_VARIABLE, {"id": str(variable)}), *unsearched)
    if len(found) > 1:
        return (Issue(CoreErrorCode.ID_DUPLICATE, {"id": str(variable)}),)
    return found[0]


def _variables_problem(path: PurePosixPath, document: JsonObject) -> tuple[Issue, ...]:
    """Why a ``.vars`` file has no list of variables to look in, as reading it says."""
    issues = validate(VARIABLES_SCHEMA, document, Location(path, file_id=file_id(document)))
    return tuple(issue for issue in issues if issue.params.get("field") == VARIABLES_FIELD)


def _object(path: PurePosixPath, content: bytes) -> Document | Issue:
    """The JSON object a file holds, or the issue that says it holds none."""
    location = Location(path)
    document = decode(content, location)
    if isinstance(document, Issue):
        return document
    if not is_object(document):
        return Issue(CoreErrorCode.FILE_NOT_AN_OBJECT, location=location)
    return document


def _indices_with_id(items: object, wanted: UUID) -> Iterator[int]:
    if not is_array(items):
        return
    for index, item in enumerate(items):
        if is_object(item) and _is_id(item.get(ID_FIELD), wanted):
            yield index


def _is_id(value: object, wanted: UUID) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return UUID(value) == wanted
    except ValueError:
        return False


def _variable_issues(path: PurePosixPath, steps: tuple[Step, ...]) -> IssuesOf:
    """The problems of the variable at ``steps``, on its own: the ones ``primum validate``
    gives about it, whatever the rest of its file has. A problem elsewhere in the file does
    not hide this variable's, nor does it count against an operation on it.

    A field the schema finds fault with (one it does not know, as a newer Primum writes, or
    one of the wrong type) does not hide the rest either: the values are checked on the
    variable without it, as long as what is left is a variable."""

    def issues_of(document: JsonObject) -> frozenset[Issue]:
        location = Location(path, file_id=file_id(document))
        variable = _at(document, steps)
        malformed = frozenset(_validated_variable(variable, location, steps))
        rest = _without_faulty_fields(variable, malformed, steps)
        if rest is None or _validated_variable(rest, location, steps):
            return malformed
        return malformed | frozenset(check_variable(parse_variable(rest), steps, location))

    return issues_of


def _validated_variable(
    variable: object, location: Location, steps: tuple[Step, ...]
) -> tuple[Issue, ...]:
    return validate_definition(VARIABLES_SCHEMA, VARIABLE_DEFINITION, variable, location, steps)


def _without_faulty_fields(
    variable: object, issues: frozenset[Issue], steps: tuple[Step, ...]
) -> JsonObject | None:
    """The variable without the fields that ``issues`` point at, or ``None`` if it is no
    object."""
    if not is_object(variable):
        return None
    faulty = {issue.location.pointer for issue in issues if issue.location}
    return {
        name: value for name, value in variable.items() if pointer((*steps, name)) not in faulty
    }


def _definition(schema: str, definition: str) -> JsonObject:
    return as_object(as_object(SCHEMAS[schema]["$defs"])[definition])


def _field_order(schema: JsonObject) -> Sequence[str]:
    return tuple(as_object(schema["properties"]))


def _at(document: object, steps: tuple[Step, ...]) -> object:
    for step in steps:
        document = as_list(document)[step] if isinstance(step, int) else as_object(document)[step]
    return document


def _changed(
    document: object,
    steps: tuple[Step, ...],
    order: Sequence[str],
    kind: _Kind,
    operation: JsonObject,
) -> object:
    """``document`` with the object at ``steps`` changed as ``operation`` says."""
    if not steps:
        return _edited(as_object(document), order, kind, operation)
    step, *rest = steps
    if isinstance(step, int):
        items = as_list(document)
        changed = _changed(items[step], tuple(rest), order, kind, operation)
        return [*items[:step], changed, *items[step + 1 :]]
    fields = as_object(document)
    return {**fields, step: _changed(fields[step], tuple(rest), order, kind, operation)}


def _edited(
    fields: JsonObject, order: Sequence[str], kind: _Kind, operation: JsonObject
) -> JsonObject:
    """The fields the operation sets, set, and the ones it clears, gone; written in the order
    of the schema, so a file reads the same whoever edited it. A field the schema does not
    know (a misspelling) is kept, after the others: it is a problem to show, not to lose."""
    cleared = as_list(operation.get(CLEAR_FIELD, []))
    set_ = {
        name: _as_json_means(value) for name, value in operation.items() if name in kind.settable
    }
    merged = {**fields, **set_}
    known = [name for name in order if name in merged]
    unknown = [name for name in merged if name not in order]
    return {name: merged[name] for name in (*known, *unknown) if name not in cleared}


def _as_json_means(value: object) -> object:
    """A number as reading a file takes it: ``2.0`` is the integer ``2`` (``formats``)."""
    return int(value) if isinstance(value, float) and value.is_integer() else value


def _holds_only_json(value: object) -> bool:
    """Whether ``value`` can be written as JSON. Reading a file keeps a number JSON does not
    have (``NaN``, ``1e999``) as a marker, so that its schema reports it; there is no text to
    write it back as."""
    if is_object(value):
        return all(_holds_only_json(item) for item in value.values())
    if is_array(value):
        return all(_holds_only_json(item) for item in value)
    return value is None or isinstance(value, str | int | float | bool)


def _unwritable(target: _Target, after: JsonObject) -> tuple[Issue, ...]:
    """Why a file left with a number JSON does not have cannot be written again: what its
    schema says where those numbers are. An operation that replaces them is taken."""
    location = Location(target.path, file_id=file_id(after))
    issues = validate(target.schema, after, location)
    places = {pointer(steps) for steps in _not_json_at(after, ())}
    there = tuple(issue for issue in issues if issue.location and issue.location.pointer in places)
    return tuple(sorted(there or issues, key=_by_place))


def _not_json_at(value: object, steps: tuple[Step, ...]) -> Iterator[tuple[Step, ...]]:
    if is_object(value):
        for name, item in value.items():
            yield from _not_json_at(item, (*steps, name))
    elif is_array(value):
        for index, item in enumerate(value):
            yield from _not_json_at(item, (*steps, index))
    elif not _holds_only_json(value):
        yield steps


def _dumped(document: JsonObject) -> str:
    """A document as text that does not depend on the order of its fields: two documents with
    the same text say the same, ``1``, ``1.0`` and ``true`` told apart."""
    return json.dumps(document, sort_keys=True, ensure_ascii=False)


def _written(document: JsonObject) -> bytes:
    """A file as Primum writes it: UTF-8, two spaces, a line end at the end."""
    return (json.dumps(document, indent=INDENT, ensure_ascii=False) + "\n").encode()


def _by_place(issue: Issue) -> tuple[str, str]:
    return (issue.location.pointer if issue.location else "", issue.code)
