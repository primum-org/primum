"""The deployment package: its hash, and reading one (decision 0024).

A package says its own hash: the sha256 of the rest of it in canonical form, the one of RFC
8785 (JSON Canonicalization Scheme): keys sorted, no spaces, UTF-8, text as it is, and numbers
as JavaScript writes them (``80``, ``0.00001``, ``1e-7``), so that the UI and any other
runtime compute the same hash with what their language already has.

Whoever reads a package checks it: its shape, its hash, and that it holds together (every
reference names something of the package, every field its case needs is there, every
variable starts within its limits and is only ever set within them). The hash
tells a file cut short or changed by hand; it says nothing of a package built wrong, so it is
never the only check. What needs the driver manifests and the board profile (that an action
exists and takes its arguments, a variable among them; that pins are free) is checked by the
runtime when it loads the package, with its own.
"""

import hashlib
import json
import math
from collections.abc import Iterable, Iterator, Mapping
from pathlib import PurePosixPath
from uuid import UUID

from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.formats import Parsed, decode
from primum_core.generated.model import (
    Command,
    Package,
    PackageAction,
    PackageAutomation,
    PackageElement,
    PackageEvent,
    PackageSequence,
    PackageVariable,
    parse_package,
)
from primum_core.json_values import as_object, is_array, is_object
from primum_core.pointers import Step, field_name, pointer
from primum_core.schema_validation import validate
from primum_core.values import EXPECTED, NUMERIC, Value, fits
from primum_core.variants import ACTION_CASES, ELEMENT_CASES, EVENT_CASES

HASH_FIELD = "hash"
SCHEMA = "package.schema.json"
# Beyond these a number is not written as plain digits (ECMAScript's Number::toString).
MAX_PLAIN_EXPONENT, MIN_PLAIN_EXPONENT = 21, -6
MAX_EXACT_INTEGER = 2**53


def package_hash(document: Mapping[str, object]) -> str:
    """The hash of a package: of everything in ``document`` but its ``hash``."""
    hashed = {key: value for key, value in document.items() if key != HASH_FIELD}
    return "sha256:" + hashlib.sha256(canonical(hashed).encode("utf-8")).hexdigest()


def canonical(value: object) -> str:
    """``value`` as canonical JSON (RFC 8785). Keys are sorted by their UTF-16 units, as
    JavaScript compares text and the RFC asks: not Python's order beyond the basic plane."""
    if is_object(value):
        keys = sorted(value, key=lambda key: key.encode("utf-16-be"))
        members = (f"{_text(key)}:{canonical(value[key])}" for key in keys)
        return "{" + ",".join(members) + "}"
    if is_array(value):
        return "[" + ",".join(canonical(item) for item in value) + "]"
    if value is None or isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, int):
        return str(value) if abs(value) < MAX_EXACT_INTEGER else _number(float(value))
    if isinstance(value, float):
        return _number(value)
    raise TypeError(f"{type(value).__name__} is not a JSON value")


def _text(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _number(number: float) -> str:
    """A number as JavaScript writes it: the shortest digits that read back to it, plain from
    1e-6 up to 1e21 and with an exponent outside."""
    if not math.isfinite(number):
        raise ValueError("JSON has no such number")
    if number == 0:
        return "0"
    sign = "-" if number < 0 else ""
    mantissa, _, exponent = repr(abs(number)).partition("e")
    whole, _, fraction = mantissa.partition(".")
    written = whole + fraction
    digits = written.lstrip("0")
    # The number is 0.<digits> x 10^point.
    point = len(whole) + int(exponent or 0) - (len(written) - len(digits))
    digits = digits.rstrip("0")
    if len(digits) <= point <= MAX_PLAIN_EXPONENT:
        return sign + digits + "0" * (point - len(digits))
    if 0 < point <= MAX_PLAIN_EXPONENT:
        return f"{sign}{digits[:point]}.{digits[point:]}"
    if MIN_PLAIN_EXPONENT < point <= 0:
        return f"{sign}0.{'0' * -point}{digits}"
    power = point - 1
    rest = f".{digits[1:]}" if len(digits) > 1 else ""
    return f"{sign}{digits[0]}{rest}e{'+' if power > 0 else '-'}{abs(power)}"


def whole_numbers(value: object) -> object:
    """``value`` with every whole number as an integer, all the way in: how a package is
    written (``80``, never ``80.0``)."""
    if is_object(value):
        return {key: whole_numbers(item) for key, item in value.items()}
    if is_array(value):
        return [whole_numbers(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def read_package(path: PurePosixPath, content: bytes) -> Parsed[Package]:
    """Read a deployment package: its shape, that its hash is the hash of the rest, and that
    it holds together."""
    location = Location(path)
    document = decode(content, location)
    if isinstance(document, Issue):
        return Parsed(None, (document,))
    issues = validate(SCHEMA, document, location)
    if issues:
        return Parsed(None, issues)
    if not is_object(document) or document[HASH_FIELD] != package_hash(document):
        at = Location(path, "/" + HASH_FIELD)
        return Parsed(None, (Issue(CoreErrorCode.PACKAGE_HASH_MISMATCH, {}, at),))
    package = parse_package(as_object(document))
    issues = tuple(check_package(package, location))
    return Parsed(None, issues) if issues else Parsed(package)


def check_package(package: Package, location: Location) -> Iterator[Issue]:
    """What a package that fits its schema may still have wrong inside: an id twice, a
    reference to nothing, a field missing for its case or one that does not belong, an
    argument or an option twice, a command outside the time of its sequence, a variable that
    starts outside its limits or is set outside them."""
    check = _Check(location)
    elements = check.ids("elements", (element.id for element in package.elements))
    check.ids("variables", (variable.id for variable in package.variables))
    variables = {variable.id: variable for variable in package.variables}
    sequences = check.ids("sequences", (sequence.id for sequence in package.sequences))
    events = check.ids("events", (event.id for event in package.events))
    schedules = check.ids("schedules", (schedule.id for schedule in package.schedules))
    check.ids("automations", (automation.id for automation in package.automations))
    yield from check.issues
    for index, element in enumerate(package.elements):
        yield from _wiring_issues(element, ("elements", index), check)
        options = [option.name for option in element.config]
        for number in _repeated(options):
            params = {"element": element.name, "option": options[number]}
            at = check.at("elements", index, "config", number)
            yield Issue(CoreErrorCode.CONFIG_DUPLICATE, params, at)
    for index, variable in enumerate(package.variables):
        yield from _variable_issues(variable, ("variables", index), check)
    names = {element.id: element.name for element in package.elements}
    for index, sequence in enumerate(package.sequences):
        for number, command in enumerate(sequence.commands):
            steps = ("sequences", index, "commands", number)
            yield from _command_issues(command, steps, elements, frozenset(variables), check)
            yield from _time_issues(command, sequence, steps, check)
            given = [argument.name for argument in command.arguments]
            for repeated in _repeated(given):
                params = {
                    "action": command.action,
                    "element": names.get(command.element, str(command.element)),
                    "parameter": given[repeated],
                }
                at = check.at(*steps, "arguments", repeated)
                yield Issue(CoreErrorCode.ACTION_PARAM_DUPLICATE, params, at)
    for index, event in enumerate(package.events):
        yield from _event_issues(event, ("events", index), elements, check)
    for index, automation in enumerate(package.automations):
        steps = ("automations", index)
        yield from _automation_issues(automation, steps, events | schedules, check)
        for number, action in enumerate(automation.do):
            at = (*steps, "do", number)
            yield from _action_issues(action, at, sequences, frozenset(variables), check)
            yield from _assignment_issues(action, at, variables, check)


class _Check:
    """Where the package is, and the ids seen so far: one id names one thing."""

    def __init__(self, location: Location) -> None:
        self._location = location
        self._seen: set[UUID] = set()
        self.issues: list[Issue] = []

    def ids(self, field: str, ids: Iterable[UUID]) -> frozenset[UUID]:
        """The ids of one list of the package, each reported if it was seen before."""
        own: set[UUID] = set()
        for index, id_ in enumerate(ids):
            if id_ in self._seen:
                params = {"id": str(id_)}
                self.issues.append(Issue(CoreErrorCode.ID_DUPLICATE, params, self.at(field, index)))
            self._seen.add(id_)
            own.add(id_)
        return frozenset(own)

    def at(self, *steps: Step) -> Location:
        return Location(self._location.path, pointer(steps))

    def reference(
        self, target: UUID | None, among: frozenset[UUID], steps: tuple[Step, ...]
    ) -> Iterator[Issue]:
        if target is not None and target not in among:
            params = {"field": field_name(steps), "id": str(target)}
            yield Issue(CoreErrorCode.REF_UNKNOWN, params, self.at(*steps))

    def fields(
        self,
        required: Iterable[str],
        unexpected: Iterable[str],
        present: Mapping[str, bool],
        steps: tuple[Step, ...],
    ) -> Iterator[Issue]:
        for name in sorted(required):
            if not present[name]:
                params = {"field": field_name((*steps, name))}
                yield Issue(CoreErrorCode.SCHEMA_MISSING_FIELD, params, self.at(*steps))
        for name in sorted(unexpected):
            if present[name]:
                params = {"field": field_name((*steps, name))}
                yield Issue(CoreErrorCode.SCHEMA_UNEXPECTED_FIELD, params, self.at(*steps, name))


def _wiring_issues(
    element: PackageElement, steps: tuple[Step, ...], check: _Check
) -> Iterator[Issue]:
    """An element is wired as its type is (``primum_core.variants``): a pin, or a bus and an
    address. A type this version does not know is the runtime's to refuse."""
    case = ELEMENT_CASES.get(element.type)
    if case is None:
        return
    present = {
        "pin": element.pin is not None,
        "bus": element.bus is not None,
        "address": element.address is not None,
        "activeLow": element.active_low,
    }
    yield from check.fields(case.required, case.unexpected, present, steps)


def _repeated(names: list[str]) -> Iterator[int]:
    """The index of each name that was already given before it."""
    seen: set[str] = set()
    for index, name in enumerate(names):
        if name in seen:
            yield index
        seen.add(name)


def _variable_issues(
    variable: PackageVariable, steps: tuple[Step, ...], check: _Check
) -> Iterator[Issue]:
    """A variable as the project's are (``primum_core.variants``): limits only on a number,
    the minimum not above the maximum, an initial value of its type and within them."""
    numeric = variable.type in NUMERIC
    limits = {"min": variable.min is not None, "max": variable.max is not None}
    yield from check.fields([], [] if numeric else ["min", "max"], limits, steps)
    if not fits(variable.initial, variable.type):
        params = {"field": field_name((*steps, "initial"))}
        yield Issue(EXPECTED[variable.type], params, check.at(*steps, "initial"))
    elif variable.min is not None and variable.max is not None and variable.min > variable.max:
        params = {"name": variable.name, "min": variable.min, "max": variable.max}
        yield Issue(CoreErrorCode.VARIABLE_LIMITS_INVALID, params, check.at(*steps))
    elif numeric and _outside(variable.initial, variable):
        params = {"name": variable.name, "initial": variable.initial}
        yield Issue(CoreErrorCode.VARIABLE_INITIAL_OUT_OF_RANGE, params, check.at(*steps))


def _outside(value: Value, variable: PackageVariable) -> bool:
    if isinstance(value, bool | str):
        return False
    below = variable.min is not None and value < variable.min
    return below or (variable.max is not None and value > variable.max)


def _assignment_issues(
    action: PackageAction,
    steps: tuple[Step, ...],
    variables: Mapping[UUID, PackageVariable],
    check: _Check,
) -> Iterator[Issue]:
    """What an action sets or adds fits its variable: a value of its type, set within its
    limits; only a number is incremented."""
    variable = variables.get(action.variable) if action.variable is not None else None
    if variable is None:
        return
    if action.action == "increment_variable" and variable.type not in NUMERIC:
        params = {"name": variable.name}
        at = check.at(*steps, "variable")
        yield Issue(CoreErrorCode.VARIABLE_NOT_NUMERIC, params, at)
        return
    if action.value is None:
        return
    at = check.at(*steps, "value")
    if not fits(action.value, variable.type):
        yield Issue(EXPECTED[variable.type], {"field": field_name((*steps, "value"))}, at)
    elif action.action == "set_variable" and _outside(action.value, variable):
        params = {"name": variable.name, "value": action.value}
        yield Issue(CoreErrorCode.VARIABLE_SET_OUT_OF_RANGE, params, at)


def _time_issues(
    command: Command, sequence: PackageSequence, steps: tuple[Step, ...], check: _Check
) -> Iterator[Issue]:
    """A command lies within the time of its sequence: its action is over by the end, and so
    is its time in force, unless it has none (what a sequence that holds keeps)."""
    if command.at_ms + command.duration_ms > sequence.duration_ms:
        params = {"field": field_name((*steps, "atMs"))}
        yield Issue(CoreErrorCode.SCHEMA_INVALID_VALUE, params, check.at(*steps, "atMs"))
    elif command.until_ms is not None and command.until_ms > sequence.duration_ms:
        params = {"field": field_name((*steps, "untilMs"))}
        yield Issue(CoreErrorCode.SCHEMA_INVALID_VALUE, params, check.at(*steps, "untilMs"))


def _command_issues(
    command: Command,
    steps: tuple[Step, ...],
    elements: frozenset[UUID],
    variables: frozenset[UUID],
    check: _Check,
) -> Iterator[Issue]:
    yield from check.reference(command.element, elements, (*steps, "element"))
    if command.until_ms is not None and command.until_ms < command.at_ms:
        params = {"field": field_name((*steps, "untilMs"))}
        yield Issue(CoreErrorCode.SCHEMA_INVALID_VALUE, params, check.at(*steps, "untilMs"))
    for index, argument in enumerate(command.arguments):
        at = (*steps, "arguments", index)
        has_value, has_variable = argument.value is not None, argument.variable is not None
        # A value or a variable: one of the two.
        if not has_value:
            yield from check.fields(["variable"], [], {"variable": has_variable}, at)
        else:
            yield from check.fields([], ["variable"], {"variable": has_variable}, at)
        yield from check.reference(argument.variable, variables, (*at, "variable"))


def _event_issues(
    event: PackageEvent, steps: tuple[Step, ...], elements: frozenset[UUID], check: _Check
) -> Iterator[Issue]:
    case = EVENT_CASES[event.source]
    present = {"element": event.element is not None, "trigger": event.trigger is not None}
    yield from check.fields(case.required, case.unexpected, present, steps)
    yield from check.reference(event.element, elements, (*steps, "element"))


def _automation_issues(
    automation: PackageAutomation, steps: tuple[Step, ...], sources: frozenset[UUID], check: _Check
) -> Iterator[Issue]:
    for index, source in enumerate(automation.when):
        yield from check.reference(source, sources, (*steps, "when", index))


def _action_issues(
    action: PackageAction,
    steps: tuple[Step, ...],
    sequences: frozenset[UUID],
    variables: frozenset[UUID],
    check: _Check,
) -> Iterator[Issue]:
    case = ACTION_CASES[action.action]
    present = {
        "sequence": action.sequence is not None,
        "variable": action.variable is not None,
        "value": action.value is not None,
    }
    yield from check.fields(case.required, case.unexpected, present, steps)
    yield from check.reference(action.sequence, sequences, (*steps, "sequence"))
    yield from check.reference(action.variable, variables, (*steps, "variable"))
