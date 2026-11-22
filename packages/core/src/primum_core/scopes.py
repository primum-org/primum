"""Names of constants and variables, scoped by folder (decision 0005).

A ``.vars`` file defines names for the folder it is in. A file sees the names of its folder and
of the folders above it, never those of sibling or child folders. A folder may export a name;
another folder uses it only after importing it (by the ``.vars`` file's id and the name). Two
different definitions with the same name, visible from one place, are an error: no shadowing.
An import of a definition that is already visible is redundant, not a conflict. The parameters
of a sequence are its innermost scope and follow the same rule.

Names are used by automations: the variable an action sets or increments, and the names of a
condition (``primum_core.expressions``), which must make sense with the types those names have.
And by sequences: an argument of a clip or of a block may take its value from a name
(``valueOf``, decision 0024). A name nothing uses is a warning.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID

from primum_core import expressions
from primum_core.errors import CoreErrorCode, Issue, Location, Severity
from primum_core.generated.model import Automation, Sequence, Variables
from primum_core.pointers import Step, pointer
from primum_core.references import LocatedContent
from primum_core.values import NUMERIC, Value, check_value

# The actions that name a variable; elsewhere a stray ``variable`` is the variants check's.
VARIABLE_ACTIONS = frozenset({"set_variable", "increment_variable"})


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
    value: Value | None = None  # a constant's
    min: float | None = None  # a variable's limits
    max: float | None = None


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
        elif _conflict(entry, existing):
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
    scopes, definitions = _scopes_of(files)
    _check_outer_scopes(scopes)
    for file in files:
        match file.content:
            case Automation():
                _use(file.content, file.location, scopes)
            case Sequence():
                _check_parameters(file.content, file.location, scopes)
                _use_in_sequence(file.content, file.location, scopes)
            case _:
                pass
    scopes.issues += _unused(definitions.values(), scopes.used)
    return tuple(scopes.issues)


def visible_definitions(files: Iterable[LocatedContent]) -> dict[UUID, Mapping[str, Definition]]:
    """The constants and variables each sequence and automation sees, by name, by the file's
    id: those of its folder and of the folders above."""
    files = tuple(files)
    scopes, _ = _scopes_of(files)
    return {
        file.content.id: {
            name: entry.definition
            for name, entry in scopes.visible(file.location.path.parent).items()
        }
        for file in files
        if isinstance(file.content, Sequence | Automation)
    }


def _scopes_of(files: tuple[LocatedContent, ...]) -> tuple[_Scopes, _Definitions]:
    """The names of each folder: defined in it or imported into it."""
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
    return scopes, definitions


def _at(location: Location, *steps: Step) -> Location:
    return replace(location, pointer=pointer(steps))


def _conflict(entry: _Entry, existing: _Entry) -> bool:
    """Two entries clash when they stand for different definitions: importing a definition that
    is already visible (from the folder above, or into it) names the same one."""
    return entry.definition.id != existing.definition.id


def _redefined(entry: _Entry, existing: _Entry) -> Issue:
    """``other`` is the file that defines the existing name, where a rename would go."""
    params = {"name": entry.definition.name, "other": str(existing.definition.location.path)}
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
            value=constant.value,
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
            min=variable.min,
            max=variable.max,
        )
        for index, variable in enumerate(content.variables)
    ]
    defined: dict[str, Definition] = {}
    for definition in definitions:
        if expressions.is_reserved(definition.name):
            # In a condition the word would win, and the name would never be read.
            at = replace(definition.location, pointer=f"{definition.location.pointer}/name")
            scopes.issues.append(Issue(CoreErrorCode.NAME_RESERVED, {"name": definition.name}, at))
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
                if existing is not None and _conflict(entry, existing):
                    scopes.issues.append(_redefined(entry, existing))
                    break


def _use(automation: Automation, location: Location, scopes: _Scopes) -> None:
    """Resolve the names an automation uses, and check what it does with them."""
    visible = scopes.visible(location.path.parent)
    if automation.if_ is not None:
        _use_in_condition(automation.if_, _at(location, "if"), visible, scopes)
    for index, action in enumerate(automation.do):
        if action.action not in VARIABLE_ACTIONS or action.variable is None:
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


def _use_in_condition(
    text: str, at: Location, visible: Mapping[str, _Entry], scopes: _Scopes
) -> None:
    """A condition must be readable, use only names it sees, fit their types and say yes or
    no. The first thing wrong with it is reported; unknown names, all of them."""
    tree = expressions.parse(text)
    if isinstance(tree, expressions.Problem):
        scopes.issues.append(Issue(tree.code, tree.params, at))
        # What it meant to use still counts: one mistake is not also a name nothing uses.
        words = expressions.words_in(text)
        scopes.used.update(visible[word].definition.id for word in words if word in visible)
        return
    names = expressions.names_in(tree)
    unknown = [name for name in names if name not in visible]
    scopes.issues += (Issue(CoreErrorCode.NAME_UNKNOWN, {"name": name}, at) for name in unknown)
    definitions = [visible[name].definition for name in names if name in visible]
    scopes.used.update(definition.id for definition in definitions)
    if unknown:
        return
    result = expressions.check(
        tree,
        {definition.name: definition.value_type for definition in definitions},
        {
            definition.name: definition.value
            for definition in definitions
            if definition.value is not None
        },
    )
    if isinstance(result, expressions.Problem):
        scopes.issues.append(Issue(result.code, result.params, at))
    elif result != expressions.BOOLEAN:
        scopes.issues.append(Issue(CoreErrorCode.EXPRESSION_NOT_A_CONDITION, {}, at))


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
    if value is None:
        return
    issue = check_value(value, variable.value_type, (*steps, "value"), location)
    if issue is not None:
        yield issue
    elif action == "set_variable" and _outside(value, variable):
        params = {"name": variable.name, "value": value}
        at = _at(location, *steps, "value")
        yield Issue(CoreErrorCode.VARIABLE_SET_OUT_OF_RANGE, params, at)


def _outside(value: Value, variable: Definition) -> bool:
    """Whether a number lies outside the limits the variable has."""
    if isinstance(value, bool | str):
        return False
    below = variable.min is not None and value < variable.min
    return below or (variable.max is not None and value > variable.max)


def _check_parameters(sequence: Sequence, location: Location, scopes: _Scopes) -> None:
    """Parameters are the innermost scope: unique, and never a name the folder sees."""
    visible = scopes.visible(location.path.parent)
    seen: dict[str, Location] = {}
    for index, parameter in enumerate(sequence.parameters):
        at = _at(location, "parameters", index)
        other = seen.get(parameter.name)
        if other is None:
            entry = visible.get(parameter.name)
            other = entry.definition.location if entry is not None else None
        if other is None:
            seen[parameter.name] = at
            continue
        params = {"name": parameter.name, "other": str(other.path)}
        scopes.issues.append(Issue(CoreErrorCode.NAME_REDEFINED, params, at))


def _use_in_sequence(sequence: Sequence, location: Location, scopes: _Scopes) -> None:
    """Resolve the names a sequence takes values from (``valueOf``), in the arguments of its
    clips and of its blocks: a parameter of its own that is not an element, or a constant or
    a variable its folder sees."""
    visible = scopes.visible(location.path.parent)
    parameters = {parameter.name: parameter.type for parameter in sequence.parameters}
    taken: list[tuple[str, tuple[Step, ...]]] = []
    for track_index, track in enumerate(sequence.tracks):
        for clip_index, clip in enumerate(track.clips):
            for index, argument in enumerate(clip.arguments):
                if argument.value_of is not None:
                    steps = ("tracks", track_index, "clips", clip_index, "arguments", index)
                    taken.append((argument.value_of, steps))
    for block_index, block in enumerate(sequence.blocks):
        for index, argument in enumerate(block.arguments):
            if argument.value_of is not None:
                taken.append((argument.value_of, ("blocks", block_index, "arguments", index)))
    for name, steps in taken:
        at = _at(location, *steps, "valueOf")
        if name in parameters:
            if parameters[name] == "element":
                scopes.issues.append(Issue(CoreErrorCode.NAME_NOT_A_VALUE, {"name": name}, at))
        elif name in visible:
            scopes.used.add(visible[name].definition.id)
        else:
            scopes.issues.append(Issue(CoreErrorCode.NAME_UNKNOWN, {"name": name}, at))


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
