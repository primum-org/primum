"""An event that listens to an element, against the manifest of its driver.

As a clip asks an element for an action its driver declares (``primum_core.actions``), an
event listens for something its driver says the element tells: turning on, or off
(``triggers`` in the manifest). An element whose type has no driver yet tells nothing. That
the element is of a type that is listened to at all, and not an output, is checked with the
references (``ref.wrong_kind``).
"""

from collections.abc import Iterable, Iterator
from dataclasses import replace
from uuid import UUID

from primum_core.drivers import Drivers
from primum_core.errors import CoreErrorCode, Issue
from primum_core.generated.model import Element, Event, Hardware
from primum_core.references import INPUT_TYPES, LocatedContent


def check_events(files: Iterable[LocatedContent], drivers: Drivers) -> Iterator[Issue]:
    """Every event that listens to an element for what it does not tell
    (``event.trigger_unavailable``, with the ``element``, the ``trigger`` and those
    ``available``), at the event's ``element``."""
    files = tuple(files)
    elements: dict[UUID, Element] = {
        element.id: element
        for file in files
        if isinstance(file.content, Hardware)
        for element in file.content.elements
    }
    for file in files:
        event = file.content
        if not isinstance(event, Event) or event.element is None or event.trigger is None:
            continue
        element = elements.get(event.element)
        # An unknown id, or an element of a type that is never listened to (an output), is
        # the references' to report.
        if element is None or element.type not in INPUT_TYPES["element"]:
            continue
        available = triggers_of(element.type, drivers)
        if event.trigger not in available:
            params = {"element": element.name, "trigger": event.trigger, "available": available}
            at = replace(file.location, pointer="/element")
            yield Issue(CoreErrorCode.EVENT_TRIGGER_UNAVAILABLE, params, at)


def triggers_of(element_type: str, drivers: Drivers) -> tuple[str, ...]:
    """What an element of this type tells; nothing for a type without a driver."""
    driver = drivers.get(element_type)
    return () if driver is None else tuple(driver.triggers)
