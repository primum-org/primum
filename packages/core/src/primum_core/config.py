"""The configuration of each element, against the manifest of its driver.

An element of a ``.hw`` file may give its driver's options by name (``frequencyHz`` of a PWM
output, ``pull`` and ``debounceMs`` of a digital input); the ones it does not give take the
driver's default. A type without a manifest takes no options.
"""

from collections.abc import Iterator

from primum_core.drivers import Drivers
from primum_core.errors import CoreErrorCode, Issue
from primum_core.generated.model import Hardware
from primum_core.given import GivenCodes, Where, check_given
from primum_core.references import LocatedContent

CONFIG = "config"
CONFIG_CODES = GivenCodes(
    key="option",
    unknown=CoreErrorCode.CONFIG_UNKNOWN,
    duplicate=CoreErrorCode.CONFIG_DUPLICATE,
    missing=CoreErrorCode.CONFIG_MISSING,
    out_of_range=CoreErrorCode.CONFIG_OUT_OF_RANGE,
    not_allowed=CoreErrorCode.CONFIG_NOT_ALLOWED,
)


def check_config(file: LocatedContent, drivers: Drivers) -> Iterator[Issue]:
    """Every option of the file's elements that its driver does not take as given."""
    if not isinstance(file.content, Hardware):
        return
    for index, element in enumerate(file.content.elements):
        driver = drivers.get(element.type)
        declared = driver.config if driver is not None else ()
        where = Where(file.location, ("elements", index), CONFIG)
        context = {"element": element.name}
        yield from check_given(element.config, declared, CONFIG_CODES, context, where)
