"""Compile a project into a deployment package (decision 0024).

The package is the project as the runtime needs it: for one board, flat, with nothing left to
look up. Components are expanded into the sequences that include them, and each sequence's
clips become commands by the rule of decision 0017 (``primum_core.commands``), so the engine
does not work out again what replaces what. Constants and the parameters of components are
put in place; a variable stays a reference, read while running. Every element carries every
option of its driver, and every command every parameter of its action, defaults included.
Names are gone: an automation says which variable it sets by its id.

Only a project that passed every check is compiled (a ``Workspace``). What is left to refuse
is what a project may be but a package cannot yet: a project without a board, or on several.
"""

from collections.abc import Iterator, Mapping
from uuid import UUID

from primum_core import expressions
from primum_core.commands import Span, Timeline, timeline_of
from primum_core.drivers import Drivers
from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.formats import Parsed
from primum_core.generated.model import (
    Automation,
    DriverParameter,
    Element,
    Event,
    Hardware,
    HardwareBoard,
    Schedule,
    Variables,
)
from primum_core.given import Fixed, FromVariable
from primum_core.json_values import is_object
from primum_core.package import HASH_FIELD, package_hash, whole_numbers
from primum_core.references import LocatedContent
from primum_core.scopes import Definition, visible_definitions
from primum_core.sources import Names
from primum_core.timeline import FlatClip, duration, flatten_all, sequences_of
from primum_core.values import Value
from primum_core.workspace import MANIFEST, Workspace

type Document = dict[str, object]

SCHEMA_VERSION = 1


def compile_package(workspace: Workspace) -> Parsed[Document]:
    """The deployment package of a valid project, as the JSON document to write, or why it
    cannot be built. Compiled with the driver manifests the project was checked against."""
    drivers = workspace.drivers
    files = [
        LocatedContent(file.content, Location(file.path, file_id=file.content.id))
        for file in workspace.files
    ]
    contents = [file.content for file in files]
    boards = [
        board for content in contents if isinstance(content, Hardware) for board in content.boards
    ]
    if len(boards) != 1:
        return Parsed(None, (_board_issue(boards, workspace),))
    elements = [
        e for content in contents if isinstance(content, Hardware) for e in content.elements
    ]
    visible = visible_definitions(files)
    content: Document = {
        "kind": "package",
        "schemaVersion": SCHEMA_VERSION,
        "project": {"id": str(workspace.manifest.id), "name": workspace.manifest.name},
        "board": {"id": str(boards[0].id), "name": boards[0].name, "model": boards[0].model},
        "elements": [_element(element, drivers) for element in elements],
        "variables": [v for c in contents if isinstance(c, Variables) for v in _variables(c)],
        "sequences": list(
            _sequences(files, drivers, {element.id: element for element in elements})
        ),
        "events": [_event(content) for content in contents if isinstance(content, Event)],
        "schedules": [_schedule(content) for content in contents if isinstance(content, Schedule)],
        "automations": [
            _automation(content, visible.get(content.id, {}))
            for content in contents
            if isinstance(content, Automation)
        ],
    }
    package = whole_numbers(content)
    if not is_object(package):
        raise TypeError("a package is an object")
    package[HASH_FIELD] = package_hash(package)
    return Parsed(package)


def _board_issue(boards: list[HardwareBoard], workspace: Workspace) -> Issue:
    location = Location(MANIFEST, file_id=workspace.manifest.id)
    if not boards:
        return Issue(CoreErrorCode.PACKAGE_NO_BOARD, {}, location)
    names = tuple(board.name for board in boards)
    return Issue(CoreErrorCode.PACKAGE_SEVERAL_BOARDS, {"boards": names}, location)


def _element(element: Element, drivers: Drivers) -> Document:
    driver = drivers.get(element.type)
    given: dict[str, Value] = {option.name: option.value for option in element.config}
    compiled: Document = {"id": str(element.id), "name": element.name, "type": element.type}
    wiring = {"pin": element.pin, "bus": element.bus, "address": element.address}
    compiled.update({key: value for key, value in wiring.items() if value is not None})
    if element.active_low:
        compiled["activeLow"] = True
    compiled["config"] = list(_with_defaults(given, driver.config if driver else ()))
    return compiled


def _with_defaults(
    given: Mapping[str, Value], parameters: tuple[DriverParameter, ...]
) -> Iterator[Document]:
    """A value for each parameter: the one given, or its default. An optional one that was
    left out is left out."""
    for parameter in parameters:
        value = given.get(parameter.name, parameter.default)
        if value is not None:
            yield {"name": parameter.name, "value": value}


def _variables(content: Variables) -> Iterator[Document]:
    for variable in content.variables:
        compiled: Document = {
            "id": str(variable.id),
            "name": variable.name,
            "type": variable.type,
            "initial": variable.initial,
            "persistent": variable.persistent,
            "setting": variable.setting,
        }
        limits = {"min": variable.min, "max": variable.max}
        compiled.update({key: limit for key, limit in limits.items() if limit is not None})
        yield compiled


def _sequences(
    files: list[LocatedContent], drivers: Drivers, elements: Mapping[UUID, Element]
) -> Iterator[Document]:
    """Every sequence that can be started: the ones without parameters. A component is only
    ever included, and is already inside the sequences that include it."""
    sequences = sequences_of(files)
    flattened = flatten_all(sequences)
    names = Names(files)
    for sequence_id, (sequence, _) in sequences.items():
        if sequence.parameters:
            continue
        clips = flattened[sequence_id]
        timeline = timeline_of(sequence, clips)
        compiled: Document = {"id": str(sequence.id), "name": sequence.name}
        compiled["priority"] = sequence.priority
        if sequence.exclusive_group is not None:
            compiled["exclusiveGroup"] = sequence.exclusive_group
        compiled["whenDone"] = sequence.when_done
        compiled["whenStartedAgain"] = sequence.when_started_again
        compiled["durationMs"] = duration(clips)
        compiled["commands"] = _commands(timeline, drivers, elements, names)
        yield compiled


def _commands(
    timeline: Timeline, drivers: Drivers, elements: Mapping[UUID, Element], names: Names
) -> list[Document]:
    """The commands of a sequence, in the order they start; those of one instant, by element
    and then by clip, so that the same project always gives the same package."""
    spans = [(element, span) for element, of in timeline.spans.items() for span in of]
    spans.sort(key=lambda item: (item[1].start, str(item[0]), str(item[1].clip.id)))
    return [_command(elements[element], span, drivers, names) for element, span in spans]


def _command(element: Element, span: Span, drivers: Drivers, names: Names) -> Document:
    clip = span.clip
    compiled: Document = {
        "clip": str(clip.id),
        "element": str(element.id),
        "atMs": span.start,
        "durationMs": clip.duration_ms,
    }
    if span.until is not None:
        compiled["untilMs"] = span.until
    compiled["action"] = clip.action
    action = next(a for a in drivers[element.type].actions if a.name == clip.action)
    compiled["arguments"] = list(_arguments(span.flat, action.parameters, names))
    return compiled


def _arguments(
    flat: FlatClip | None, parameters: tuple[DriverParameter, ...], names: Names
) -> Iterator[Document]:
    """A value, or the variable to read it from, for each parameter of the action."""
    if flat is None:
        raise ValueError("a span without its clip: the timeline was not made by timeline_of")
    given = {argument.name: argument for argument in flat.clip.arguments}
    for parameter in parameters:
        argument = given.get(parameter.name)
        if argument is None:
            if parameter.default is not None:
                yield {"name": parameter.name, "value": parameter.default}
            continue
        match names.of_argument(argument, flat.origin, dict(flat.values)):
            case Fixed(value):
                yield {"name": parameter.name, "value": value}
            case FromVariable(id=variable):
                yield {"name": parameter.name, "variable": str(variable)}
            case _:
                # The checks refuse a name that stands for nothing and a parameter nobody gives.
                raise ValueError(f"argument {parameter.name} of clip {flat.clip.id} has no value")


def _event(event: Event) -> Document:
    compiled: Document = {"id": str(event.id), "name": event.name, "source": event.source}
    if event.element is not None:
        compiled["element"] = str(event.element)
    if event.trigger is not None:
        compiled["trigger"] = event.trigger
    return compiled


def _schedule(schedule: Schedule) -> Document:
    return {
        "id": str(schedule.id),
        "name": schedule.name,
        "times": [{"days": list(time.days), "at": time.at} for time in schedule.times],
        "windows": [
            {"days": list(window.days), "from": window.from_, "to": window.to}
            for window in schedule.windows
        ],
    }


def _condition(text: str, visible: Mapping[str, Definition]) -> list[dict[str, object]]:
    """The condition as a program (``primum_core.expressions``): constants in place, variables
    by id."""
    tree = expressions.parse(text)
    if isinstance(tree, expressions.Problem):  # the checks refuse it before compiling
        raise ValueError(f"condition cannot be read: {tree.code}")
    bindings: dict[str, Value | UUID] = {}
    for name in expressions.names_in(tree):
        definition = visible[name]
        bindings[name] = definition.id if definition.value is None else definition.value
    return expressions.compile_program(tree, bindings)


def _automation(automation: Automation, visible: Mapping[str, Definition]) -> Document:
    compiled: Document = {
        "id": str(automation.id),
        "name": automation.name,
        "enabled": automation.enabled,
        "when": [str(source) for source in automation.when],
    }
    if automation.if_ is not None:
        compiled["if"] = _condition(automation.if_, visible)
    do: list[Document] = []
    for action in automation.do:
        step: Document = {"action": action.action}
        if action.sequence is not None:
            step["sequence"] = str(action.sequence)
        if action.variable is not None:
            step["variable"] = str(visible[action.variable].id)
        if action.value is not None:
            step["value"] = action.value
        do.append(step)
    compiled["do"] = do
    return compiled
