"""Names of constants and variables, scoped by folder (decision 0005).

A ``.vars`` file defines names for the folder it is in. A file sees the names of its folder and
of the folders above it, never those of sibling or child folders. A folder may export a name;
another folder uses it only after importing it (by the ``.vars`` file's id and the name). A name
defined again where it is already visible, in the same folder or in an inner one, is an error:
no shadowing. The parameters of a sequence are its innermost scope and follow the same rule.

Names are used by automations: the variable an action sets or increments, and the words of a
condition (stored as text until phase 4 parses it: any word that matches a visible name counts
as a use). A name nothing uses is a warning.
"""

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID

from primum_core.errors import CoreErrorCode, Issue, Location, Severity
from primum_core.generated.model import Automation, Sequence, Variables
from primum_core.pointers import Step, pointer
from primum_core.references import LocatedContent
from primum_core.values import NUMERIC, Value, check_value

WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class Definition:
    """A constant or a variable: what a name stands for."""

    id: UUID
    name: str
    kind: Literal["constant", "variable"]
    value_type: str
    location: Location
    exported: bool = False
    setting: bool = False


@dataclass(frozen=True)
class _Entry:
    """A name in a folder's scope: its definition, and where it entered the folder (the
    definition itself or an import)."""

    definition: Definition
    location: Location


type _VarsFile = tuple[Variables, Location]
type _Definitions = Mapping[UUID, Mapping[str, Definition]]  # by .vars file id, then by name


@dataclass
class _Scopes:
    folders: dict[PurePosixPath, dict[str, _Entry]] = field(
        default_factory=dict[PurePosixPath, dict[str, _Entry]]
    )
    used: set[UUID] = field(default_factory=set[UUID])
    issues: list[Issue] = field(default_factory=list[Issue])

    def add(self, folder: PurePosixPath, entry: _Entry) -> None:
        """Enter a name in a folder, unless the folder already has it."""
        names = self.folders.setdefault(folder, {})
        existing = names.get(entry.definition.name)
        if existing is None:
            names[entry.definition.name] = entry
        else:
            self.issues.append(_redefined(entry, existing))

    def visible(self, folder: PurePosixPath) -> Mapping[str, _Entry]:
        """The names a file in ``folder`` sees: its folder's and the folders' above."""
        names: dict[str, _Entry] = {}
        for scope in (folder, *folder.parents):
            names.update(self.folders.get(scope, {}))
        return names


def check_scopes(files: Iterable[LocatedContent]) -> tuple[Issue, ...]:
    """Every problem with the names of a project, then a warning per name nothing uses."""
    files = tuple(files)
    variables: list[_VarsFile] = [
        (file.content, file.location) for file in files if isinstance(file.content, Variables)
    ]
    scopes = _Scopes()
    definitions = {
        content.id: _define(content, location, scopes) for content, location in variables
    }
    for content, location in variables:
        _export(content, location, definitions[content.id], scopes)
    for content, location in variables:
        _import(content, location, definitions, scopes)
    _check_outer_scopes(scopes)
    for file in files:
        match file.content:
            case Automation():
                _use(file.content, file.location, scopes)
            case Sequence():
                _check_parameters(file.content, file.location, scopes)
            case _:
                pass
    scopes.issues += _unused(definitions.values(), scopes.used)
    return tuple(scopes.issues)


def _at(location: Location, *steps: Step) -> Location:
    return replace(location, pointer=pointer(steps))


def _redefined(entry: _Entry, existing: _Entry) -> Issue:
    params = {"name": entry.definition.name, "other": str(existing.location.path)}
    return Issue(CoreErrorCode.NAME_REDEFINED, params, entry.location)


def _define(content: Variables, location: Location, scopes: _Scopes) -> dict[str, Definition]:
    """The definitions of one ``.vars`` file, entered in its folder."""
    exports = set(content.exports)
    definitions = [
        Definition(
            constant.id,
            constant.name,
            "constant",
            constant.type,
            _at(location, "constants", index),
            constant.name in exports,
        )
        for index, constant in enumerate(content.constants)
    ] + [
        Definition(
            variable.id,
            variable.name,
            "variable",
            variable.type,
            _at(location, "variables", index),
            variable.name in exports,
            variable.setting,
        )
        for index, variable in enumerate(content.variables)
    ]
    defined: dict[str, Definition] = {}
    for definition in definitions:
        entry = _Entry(definition, definition.location)
        existing = defined.get(definition.name)
        if existing is not None:  # twice in the same file: not entered in the folder again
            scopes.issues.append(_redefined(entry, _Entry(existing, existing.location)))
            continue
        defined[definition.name] = definition
        scopes.add(location.path.parent, entry)
    return defined


def _export(
    content: Variables, location: Location, defined: Mapping[str, Definition], scopes: _Scopes
) -> None:
    for index, name in enumerate(content.exports):
        if name not in defined:
            at = _at(location, "exports", index)
            scopes.issues.append(Issue(CoreErrorCode.NAME_UNKNOWN, {"name": name}, at))


def _import(
    content: Variables, location: Location, definitions: _Definitions, scopes: _Scopes
) -> None:
    for index, imported in enumerate(content.imports):
        source = definitions.get(imported.from_)
        if source is None:  # not a .vars file: the references check reports it
            continue
        at = _at(location, "imports", index, "name")
        definition = source.get(imported.name)
        if definition is None:
            scopes.issues.append(Issue(CoreErrorCode.NAME_UNKNOWN, {"name": imported.name}, at))
        elif not definition.exported:
            params = {"name": imported.name}
            scopes.issues.append(Issue(CoreErrorCode.NAME_NOT_EXPORTED, params, at))
        else:
            scopes.add(location.path.parent, _Entry(definition, at))


def _check_outer_scopes(scopes: _Scopes) -> None:
    """A name entered in a folder where a folder above already has it is a redefinition."""
    for folder in sorted(scopes.folders, key=lambda path: len(path.parts)):
        for name, entry in scopes.folders[folder].items():
            for above in folder.parents:
                existing = scopes.folders.get(above, {}).get(name)
                if existing is not None:
                    scopes.issues.append(_redefined(entry, existing))
                    break


def _use(automation: Automation, location: Location, scopes: _Scopes) -> None:
    """Resolve the names an automation uses, and check what it does with them."""
    visible = scopes.visible(location.path.parent)
    if automation.if_:
        for word in set(WORD.findall(automation.if_)):
            if word in visible:
                scopes.used.add(visible[word].definition.id)
    for index, action in enumerate(automation.do):
        if action.variable is None:
            continue
        steps: tuple[Step, ...] = ("do", index)
        entry = visible.get(action.variable)
        if entry is None:
            code = CoreErrorCode.NAME_UNKNOWN
        elif entry.definition.kind != "variable":
            code = CoreErrorCode.NAME_NOT_A_VARIABLE
        else:
            scopes.used.add(entry.definition.id)
            scopes.issues += _action_value_issues(
                action.action, action.value, entry.definition, steps, location
            )
            continue
        at = _at(location, *steps, "variable")
        scopes.issues.append(Issue(code, {"name": action.variable}, at))


def _action_value_issues(
    action: str,
    value: Value | None,
    variable: Definition,
    steps: tuple[Step, ...],
    location: Location,
) -> Iterator[Issue]:
    if action == "increment_variable" and variable.value_type not in NUMERIC:
        params = {"name": variable.name}
        yield Issue(CoreErrorCode.VARIABLE_NOT_NUMERIC, params, _at(location, *steps, "variable"))
        return
    if value is not None:
        issue = check_value(value, variable.value_type, (*steps, "value"), location)
        if issue is not None:
            yield issue


def _check_parameters(sequence: Sequence, location: Location, scopes: _Scopes) -> None:
    """Parameters are the innermost scope: unique, and never a name the folder sees."""
    visible = scopes.visible(location.path.parent)
    seen: dict[str, Location] = {}
    for index, parameter in enumerate(sequence.parameters):
        at = _at(location, "parameters", index)
        other = seen.get(parameter.name)
        if other is None:
            entry = visible.get(parameter.name)
            other = entry.location if entry is not None else None
        if other is None:
            seen[parameter.name] = at
            continue
        params = {"name": parameter.name, "other": str(other.path)}
        scopes.issues.append(Issue(CoreErrorCode.NAME_REDEFINED, params, at))


def _unused(definitions: Iterable[Mapping[str, Definition]], used: set[UUID]) -> list[Issue]:
    issues: list[Issue] = []
    for defined in definitions:
        for definition in defined.values():
            if definition.id in used or definition.exported or definition.setting:
                continue
            params = {"name": definition.name}
            issues.append(
                Issue(CoreErrorCode.NAME_UNUSED, params, definition.location, Severity.WARNING)
            )
    return issues
