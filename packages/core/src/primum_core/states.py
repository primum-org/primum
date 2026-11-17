"""The state each action leaves its element in, as its driver declares it (decision 0018).

A manifest gives each action an end state, a level from 0 to 100: fixed (``on`` is 100,
``off`` is 0) or given by one of its parameters (``set`` its ``level``, ``fade`` its ``to``).
It is what an instant command sets and where a clip with a length ends. An action with a start
state too moves its element from one to the other over its clip (a ``fade``).

With it ``core`` tells what two commands have in common whatever their names (an instant
``set`` to 0 is an ``off``), and warns about a clip that moves its element to rest and then
gives it back to an instant command that asks for something else: a ``fade`` to 0 under a
standing ``on`` ends with the element jumping back on, unless an instant ``off`` follows it.
"""

from collections.abc import Iterable, Mapping
from uuid import UUID

from primum_core.commands import Running, command_at, timeline_of
from primum_core.drivers import Drivers
from primum_core.errors import CoreErrorCode, Issue, Severity
from primum_core.generated.model import Clip, Driver, DriverAction, Hardware, NamedValue
from primum_core.references import LocatedContent
from primum_core.timeline import FlatClip, flatten_all, sequences_of

type _Elements = Mapping[UUID, tuple[str, Driver]]  # each element's name and driver


def end_level(clip: Clip, driver: Driver) -> float | None:
    """The level the clip leaves its element at. ``None`` when it cannot be told: an action
    the driver does not have, or arguments the actions check reports."""
    action = _action(driver, clip.action)
    return None if action is None else _level(action.end_state, action, clip.arguments)


def rest_level(driver: Driver) -> float | None:
    """The level of the driver's safe state, where its elements rest. ``None`` for a driver
    without one (an input)."""
    action = _action(driver, driver.safe_state)
    return None if action is None else _level(action.end_state, action, ())


def check_returns(files: Iterable[LocatedContent], drivers: Drivers) -> tuple[Issue, ...]:
    """Every clip that moves its element to rest and, when it ends, gives it back to an instant
    command of before (placed no later than the clip starts) that asks for another state.

    A clip is checked where its element is known: in its own sequence, or at the block that
    gives a component its element, once per different problem.
    """
    files = tuple(files)
    elements: _Elements = {
        element.id: (element.name, driver)
        for file in files
        if isinstance(file.content, Hardware)
        for element in file.content.elements
        if (driver := drivers.get(element.type)) is not None
    }
    sequences = sequences_of(files)
    flattened = flatten_all(sequences)
    issues: list[Issue] = []
    for sequence_id, (sequence, _) in sequences.items():
        clips = flattened[sequence_id]
        moving = [clip for clip in clips if _moves_to_rest(clip, elements)]
        if not moving:
            continue
        timelines = {sequence_id: timeline_of(sequence, clips)}
        running = (Running(sequence_id, 0),)
        for clip in moving:
            name, driver = elements[clip.element]
            after = command_at(clip.element, clip.end, running, timelines)
            # Nothing, or a clip with a length: nothing comes back. An instant command placed
            # after the clip started is not of before: where the clip ends it is the cure,
            # and inside the clip it cuts it, which is another matter.
            if after is None or after.clip.duration_ms > 0 or after.since_ms > clip.start:
                continue
            standing = end_level(after.clip, driver)
            if standing is None or standing == rest_level(driver):
                continue
            params = {"element": name, "action": clip.clip.action, "standing": after.clip.action}
            code = CoreErrorCode.CLIP_RETURNS_TO_INSTANT
            issues.append(Issue(code, params, clip.at, Severity.WARNING))
    return tuple(dict.fromkeys(issues))


def _moves_to_rest(clip: FlatClip, elements: _Elements) -> bool:
    """A clip with a length, of an element known here, whose action moves it from another
    state to where the element rests."""
    if clip.instant or clip.element not in elements:
        return False
    if clip.via is not None and not clip.bound_here:
        return False  # the included sequence's own, checked there
    _, driver = elements[clip.element]
    action = _action(driver, clip.clip.action)
    if action is None or action.start_state is None:
        return False
    starts = _level(action.start_state, action, clip.clip.arguments)
    ends = end_level(clip.clip, driver)
    return ends is not None and ends == rest_level(driver) and starts != ends


def _action(driver: Driver, name: str | None) -> DriverAction | None:
    return next((action for action in driver.actions if action.name == name), None)


def _level(
    state: float | str, action: DriverAction, arguments: tuple[NamedValue, ...]
) -> float | None:
    if not isinstance(state, str):
        return state
    parameter = next((p for p in action.parameters if p.name == state), None)
    if parameter is None:
        return None
    given = [argument.value for argument in arguments if argument.name == state]
    if len(given) > 1:
        return None
    value = given[0] if given else parameter.default
    return None if value is None or isinstance(value, bool | str) else value
