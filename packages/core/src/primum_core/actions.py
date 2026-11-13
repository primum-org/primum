"""The action of each clip, against the manifest of its element's driver (decision 0016).

A clip asks its element for one of the actions its driver declares, with a value for each
parameter that has no default. A track on an element whose driver has no actions (an input) is
an error: such an element is listened to, with an event, not commanded. So is a track on an
element whose type has no driver yet, with its own code: there is nothing to listen to either.

A track of a component plays a parameter, so what its clips ask can only be checked where a
block gives that parameter an element: there, at the block, once per different problem.
"""

from collections.abc import Iterable, Iterator, Mapping
from uuid import UUID

from primum_core.drivers import Drivers
from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.generated.model import Clip, DriverAction, Element, Hardware
from primum_core.given import GivenCodes, Where, check_given
from primum_core.references import LocatedContent
from primum_core.timeline import at, flatten_all, sequences_of

type _Actions = Mapping[str, DriverAction]

ARGUMENTS = "arguments"
ACTION_CODES = GivenCodes(
    key="parameter",
    unknown=CoreErrorCode.ACTION_PARAM_UNKNOWN,
    duplicate=CoreErrorCode.ACTION_PARAM_DUPLICATE,
    missing=CoreErrorCode.ACTION_PARAM_MISSING,
    out_of_range=CoreErrorCode.ACTION_PARAM_OUT_OF_RANGE,
    not_allowed=CoreErrorCode.ACTION_PARAM_NOT_ALLOWED,
)


def check_actions(files: Iterable[LocatedContent], drivers: Drivers) -> tuple[Issue, ...]:
    """Every clip that asks its element for something its driver does not offer."""
    files = tuple(files)
    elements: dict[UUID, Element] = {
        element.id: element
        for file in files
        if isinstance(file.content, Hardware)
        for element in file.content.elements
    }
    sequences = sequences_of(files)
    flattened = flatten_all(sequences)
    issues: list[Issue] = []
    for sequence_id, (sequence, location) in sequences.items():
        for track_index, track in enumerate(sequence.tracks):
            # A parameter is checked where a block binds it; an unknown id is the references'.
            element = elements.get(track.element)
            if element is None:
                continue
            steps = ("tracks", track_index)
            clips = [
                (clip, Where(location, (*steps, "clips", index), ARGUMENTS))
                for index, clip in enumerate(track.clips)
            ]
            issues += _asked(element, drivers, at(location, *steps, "element"), clips)
        for flat in flattened[sequence_id]:
            element = elements.get(flat.element)
            if element is not None and flat.bound_here:
                clips = [(flat.clip, Where(flat.at, None, ARGUMENTS))]
                issues += _asked(element, drivers, flat.at, clips)
    # A component of twenty clips bound to the wrong element is one problem per block.
    return tuple(dict.fromkeys(issues))


def _asked(
    element: Element, drivers: Drivers, place: Location, clips: Iterable[tuple[Clip, Where]]
) -> Iterator[Issue]:
    """What is wrong in what the clips ask of the element. An element that cannot be on a track
    at all is one problem, at ``place``: its type has no driver yet, or its driver has no
    actions (an input)."""
    driver = drivers.get(element.type)
    if driver is None:
        params = {"element": element.name, "type": element.type}
        yield Issue(CoreErrorCode.TRACK_ELEMENT_WITHOUT_DRIVER, params, place)
        return
    if not driver.actions:
        params = {"element": element.name}
        yield Issue(CoreErrorCode.TRACK_ELEMENT_WITHOUT_ACTIONS, params, place)
        return
    actions = {action.name: action for action in driver.actions}
    for clip, where in clips:
        yield from _clip_issues(clip, element, actions, where)


def _clip_issues(clip: Clip, element: Element, actions: _Actions, where: Where) -> Iterator[Issue]:
    context = {"action": clip.action, "element": element.name}
    action = actions.get(clip.action)
    if action is None:
        params = {**context, "available": tuple(actions)}
        yield Issue(CoreErrorCode.ACTION_UNKNOWN, params, where.at("action"))
        return
    yield from check_given(clip.arguments, action.parameters, ACTION_CODES, context, where)
