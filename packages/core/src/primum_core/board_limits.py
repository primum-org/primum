"""The options of each element, against the limits of its board.

What a board can do is data of its profile (``boards/``), taken from the manufacturer's
documentation: the frequencies its PWM takes, for one. A driver manifest says that an option
exists, its type and its default, for every platform; the profile of a board says which values
that board takes. An option the element does not give is checked with its driver's default: a
default is a value like any other, and a board may not take it.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from uuid import UUID

from primum_core.drivers import Drivers
from primum_core.errors import CoreErrorCode, Issue, Location
from primum_core.generated.model import BoardProfile, Driver, Element, Hardware, OptionLimit
from primum_core.given import shown
from primum_core.pointers import Step, pointer
from primum_core.references import LocatedContent
from primum_core.resources import Profiles
from primum_core.values import NUMERIC, Value, fits


@dataclass(frozen=True)
class _Board:
    name: str
    profile: BoardProfile


def check_board_limits(
    files: Iterable[LocatedContent], profiles: Profiles, drivers: Drivers
) -> tuple[Issue, ...]:
    """Every option of an element with a value its board does not take. A board without a
    profile is the resources check's, and so its elements are not checked here either."""
    files = tuple(files)
    boards: dict[UUID, _Board] = {
        board.id: _Board(board.name, profiles[board.model])
        for file in files
        if isinstance(file.content, Hardware)
        for board in file.content.boards
        if board.model in profiles
    }
    issues: list[Issue] = []
    for file in files:
        if not isinstance(file.content, Hardware):
            continue
        for index, element in enumerate(file.content.elements):
            board = boards.get(element.board)
            driver = drivers.get(element.type)
            if board is not None and driver is not None:
                place = replace(file.location, pointer=pointer(("elements", index)))
                issues += _element_issues(element, driver, board, place, ("elements", index))
    return tuple(issues)


def _element_issues(
    element: Element, driver: Driver, board: _Board, place: Location, steps: tuple[Step, ...]
) -> Iterator[Issue]:
    for limit in board.profile.limits:
        if limit.element_type != element.type:
            continue
        found = _value(element, driver, limit)
        if found is None:
            continue
        value, index = found
        if isinstance(value, bool | str) or limit.min <= value <= limit.max:
            continue
        params = {
            "element": element.name,
            "option": limit.option,
            "board": board.name,
            "min": shown(limit.min),
            "max": shown(limit.max),
        }
        if index is not None:
            place = replace(place, pointer=pointer((*steps, "config", index, "value")))
        yield Issue(CoreErrorCode.CONFIG_OUT_OF_BOARD_RANGE, params, place)


def _value(element: Element, driver: Driver, limit: OptionLimit) -> tuple[Value, int | None] | None:
    """The value the element has for the limited option and where it gives it (``None``: its
    driver's default). Nothing for what the configuration check reports: an option its driver
    does not have, given twice or with a value of another type."""
    option = next((option for option in driver.config if option.name == limit.option), None)
    if option is None or option.type not in NUMERIC:
        return None
    given = [
        (item.value, index)
        for index, item in enumerate(element.config)
        if item.name == limit.option
    ]
    if len(given) > 1:
        return None
    if not given:
        return None if option.default is None else (option.default, None)
    return given[0] if fits(given[0][0], option.type) else None
